using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using ATAS.Indicators;
using ATAS.Indicators.Technical;
using ATAS.Types;
using OFT.Attributes;

namespace OrderFlowV5.Indicators
{
    [DisplayName("Indicator Exporter")]
    [Category("Custom")]
    public class IndicatorExporter : Indicator
    {
        private const int AtrPeriod = 14;
        private const int FastEmaPeriod = 12;
        private const int SlowEmaPeriod = 26;
        private const int SignalEmaPeriod = 9;
        private const int RsiPeriod = 14;
        private const int VolumePercentileWindow = 200;
        private const int CvdStatsWindow = 200;
        private const int MigrationWindow = 20;
        private const decimal BasisPoint = 10000m;

        private readonly object _fileLock = new object();
        private readonly List<decimal> _cvd = new List<decimal>();
        private readonly List<decimal> _cvdForStats = new List<decimal>();
        private readonly List<decimal> _returns = new List<decimal>();
        private readonly List<decimal> _pocHistory = new List<decimal>();
        private readonly List<DateTime> _timeHistory = new List<DateTime>();
        private readonly List<decimal> _atrValues = new List<decimal>();
        private readonly List<decimal> _volumeHistory = new List<decimal>();
        private readonly List<decimal> _valueMigrationHistory = new List<decimal>();
        private readonly Dictionary<string, SessionAggregator> _sessionAggregators = new Dictionary<string, SessionAggregator>();

        private decimal _emaFast;
        private decimal _emaSlow;
        private decimal _emaSignal;
        private decimal _prevClose;

        public IndicatorExporter()
            : base(true)
        {
            DenyToChangePanel = true;
            _emaFast = 0m;
            _emaSlow = 0m;
            _emaSignal = 0m;
            _prevClose = 0m;
        }

        protected override void OnCalculate(int bar, decimal value)
        {
            if (bar < 0 || bar >= BarsCount)
            {
                return;
            }

            var candle = GetCandle(bar);
            if (candle == null)
            {
                return;
            }

            var typicalPrice = (candle.High + candle.Low + candle.Close) / 3m;
            var poc = typicalPrice;
            var vah = candle.Close + (candle.High - candle.Low) * 0.15m;
            var val = candle.Close - (candle.High - candle.Low) * 0.15m;
            var nearPoc = candle.Close - poc;
            var nearVah = candle.Close - vah;
            var nearVal = candle.Close - val;

            var sessionKey = candle.Time.ToString("yyyyMMdd");
            if (!_sessionAggregators.TryGetValue(sessionKey, out var session))
            {
                session = new SessionAggregator();
                _sessionAggregators[sessionKey] = session;
            }
            session.Add(candle.Volume, typicalPrice);

            var delta = candle.BuyVolume - candle.SellVolume;
            _cvd.Add((_cvd.Count == 0 ? 0m : _cvd.Last()) + delta);
            var cvd = _cvd.Last();
            UpdateEma(ref _emaFast, cvd, FastEmaPeriod);
            UpdateEma(ref _emaSlow, cvd, SlowEmaPeriod);
            var cvdEmaFast = _emaFast;
            var cvdEmaSlow = _emaSlow;
            var cvdMacd = cvdEmaFast - cvdEmaSlow;
            UpdateEma(ref _emaSignal, cvdMacd, SignalEmaPeriod);
            var cvdMacdSignal = _emaSignal;
            var cvdMacdHistogram = cvdMacd - cvdMacdSignal;

            if (_cvdForStats.Count >= CvdStatsWindow)
            {
                _cvdForStats.RemoveAt(0);
            }
            _cvdForStats.Add(cvd);

            var cvdRsi = ComputeRsi(_cvd.Select(x => (double)x).ToList(), RsiPeriod);
            var cvdZ = ComputeZScore(_cvdForStats);

            var upVolume = Math.Max(delta, 0m);
            var downVolume = Math.Max(-delta, 0m);
            var imbalance = upVolume - downVolume;

            _pocHistory.Add(poc);
            if (_pocHistory.Count > MigrationWindow)
            {
                _pocHistory.RemoveAt(0);
            }

            var valueMigration = _pocHistory.Count > 1 ? _pocHistory.Last() - _pocHistory[_pocHistory.Count - 2] : 0m;
            var migrationAccel = 0m;
            if (_valueMigrationHistory.Count > 0)
            {
                var prevMigration = _valueMigrationHistory.Last();
                migrationAccel = valueMigration - prevMigration;
            }
            _valueMigrationHistory.Add(valueMigration);
            if (_valueMigrationHistory.Count > MigrationWindow)
            {
                _valueMigrationHistory.RemoveAt(0);
            }

            var positiveMigrations = _valueMigrationHistory.Count(x => x > 0);
            var negativeMigrations = _valueMigrationHistory.Count(x => x < 0);
            var valueMigrationConsistency = _valueMigrationHistory.Count > 0
                ? (decimal)(positiveMigrations - negativeMigrations) / _valueMigrationHistory.Count
                : 0m;
            var valueMigrationSpeed = valueMigration / (decimal)Math.Max(1, candle.Volume);

            var nearestLvn = ComputeNearestNode(_volumeHistory, false);
            var nearestHvn = ComputeNearestNode(_volumeHistory, true);
            var inLvn = nearestLvn.HasValue && Math.Abs((double)(candle.Close - nearestLvn.Value)) <= (double)(candle.High - candle.Low) * 0.25;

            _volumeHistory.Add(candle.Volume);
            if (_volumeHistory.Count > VolumePercentileWindow)
            {
                _volumeHistory.RemoveAt(0);
            }
            var volPct = ComputePercentile(_volumeHistory, candle.Volume);

            var trueRange = ComputeTrueRange(candle, _prevClose);
            _prevClose = candle.Close;
            if (_atrValues.Count >= AtrPeriod)
            {
                _atrValues.RemoveAt(0);
            }
            _atrValues.Add(trueRange);
            var atr = _atrValues.Count > 0 ? _atrValues.Average() : trueRange;
            var atrNormRange = atr == 0m ? 0m : (candle.High - candle.Low) / atr;
            var keltnerUpper = session.Vwap + 2m * atr;
            var keltnerLower = session.Vwap - 2m * atr;
            var keltnerPos = keltnerUpper == keltnerLower ? 0m : (candle.Close - keltnerLower) / (keltnerUpper - keltnerLower);

            var vwap = session.Vwap;
            var vwapDevBps = vwap == 0m ? 0m : (candle.Close - vwap) / vwap * BasisPoint;

            var lsNorm = candle.Volume == 0m ? 0m : delta / candle.Volume;

            _timeHistory.Add(candle.Time);
            if (_timeHistory.Count > CvdStatsWindow)
            {
                _timeHistory.RemoveAt(0);
            }

            var ret = ComputeReturn(candle);
            _returns.Add(ret);
            if (_returns.Count > CvdStatsWindow)
            {
                _returns.RemoveAt(0);
            }
            var retVar = _returns.Count > 1 ? Variance(_returns) : 0m;
            var retAcf1 = Autocorrelation(_returns, 1);

            var cvdSkew = Skewness(_cvdForStats);
            var cvdKurt = Kurtosis(_cvdForStats);

            var absorptionDetected = Math.Abs(delta) < candle.Volume * 0.2m && Math.Abs(candle.Close - candle.Open) > (candle.High - candle.Low) * 0.5m;
            var absorptionStrength = absorptionDetected ? (double)(candle.Volume - Math.Abs(delta)) / Math.Max(1.0, (double)candle.Volume) : 0.0;

            var sessionId = sessionKey;

            var exportData = new Dictionary<string, object>
            {
                ["timestamp"] = candle.Time,
                ["open"] = candle.Open,
                ["high"] = candle.High,
                ["low"] = candle.Low,
                ["close"] = candle.Close,
                ["volume"] = candle.Volume,
                ["poc"] = poc,
                ["vah"] = vah,
                ["val"] = val,
                ["near_poc"] = nearPoc,
                ["near_vah"] = nearVah,
                ["near_val"] = nearVal,
                ["value_migration"] = valueMigration,
                ["value_migration_speed"] = valueMigrationSpeed,
                ["value_migration_consistency"] = valueMigrationConsistency,
                ["bar_delta"] = delta,
                ["cvd"] = cvd,
                ["cvd_ema_fast"] = cvdEmaFast,
                ["cvd_ema_slow"] = cvdEmaSlow,
                ["cvd_macd"] = cvdMacd,
                ["cvd_macd_signal"] = cvdMacdSignal,
                ["cvd_macd_hist"] = cvdMacdHistogram,
                ["cvd_rsi"] = cvdRsi,
                ["cvd_z"] = cvdZ,
                ["imbalance"] = imbalance,
                ["nearest_lvn"] = nearestLvn,
                ["nearest_hvn"] = nearestHvn,
                ["in_lvn"] = inLvn,
                ["absorption_detected"] = absorptionDetected,
                ["absorption_strength"] = absorptionStrength,
                ["vol_pctl"] = volPct,
                ["atr"] = atr,
                ["atr_norm_range"] = atrNormRange,
                ["keltner_pos"] = keltnerPos,
                ["vwap_session"] = vwap,
                ["vwap_dev_bps"] = vwapDevBps,
                ["ls_norm"] = lsNorm,
                ["session_id"] = sessionId,
                ["ret_var"] = retVar,
                ["ret_acf1"] = retAcf1,
                ["cvd_skew"] = cvdSkew,
                ["cvd_kurt"] = cvdKurt,
                ["migration_accel"] = migrationAccel
            };

            Export(exportData, candle.Time);
        }

        private decimal ComputePercentile(List<decimal> values, decimal value)
        {
            if (values.Count == 0)
            {
                return 0m;
            }

            var ordered = values.OrderBy(x => x).ToList();
            var index = ordered.FindIndex(x => x >= value);
            if (index < 0)
            {
                index = ordered.Count - 1;
            }
            return (decimal)index / Math.Max(1, ordered.Count - 1);
        }

        private decimal ComputeTrueRange(Candle candle, decimal prevClose)
        {
            var highLow = candle.High - candle.Low;
            var highClose = Math.Abs(candle.High - prevClose);
            var lowClose = Math.Abs(candle.Low - prevClose);
            return Math.Max(highLow, Math.Max(highClose, lowClose));
        }

        private decimal ComputeReturn(Candle candle)
        {
            return candle.Open == 0m ? 0m : (candle.Close - candle.Open) / candle.Open;
        }

        private void UpdateEma(ref decimal ema, decimal value, int period)
        {
            var alpha = 2m / (period + 1);
            if (ema == 0m)
            {
                ema = value;
            }
            else
            {
                ema = value * alpha + ema * (1 - alpha);
            }
        }

        private decimal ComputeRsi(List<double> values, int period)
        {
            if (values.Count < period + 1)
            {
                return 50m;
            }

            var gains = 0.0;
            var losses = 0.0;
            for (var i = values.Count - period; i < values.Count; i++)
            {
                var change = values[i] - values[i - 1];
                if (change >= 0)
                {
                    gains += change;
                }
                else
                {
                    losses -= change;
                }
            }

            if (losses == 0)
            {
                return 100m;
            }

            var rs = gains / losses;
            return (decimal)(100 - 100 / (1 + rs));
        }

        private decimal ComputeZScore(List<decimal> values)
        {
            if (values.Count == 0)
            {
                return 0m;
            }

            var mean = values.Average();
            var variance = values.Select(v => (v - mean) * (v - mean)).Average();
            var std = (decimal)Math.Sqrt((double)variance);
            if (std == 0m)
            {
                return 0m;
            }

            var latest = values.Last();
            return (latest - mean) / std;
        }

        private decimal Variance(List<decimal> values)
        {
            if (values.Count <= 1)
            {
                return 0m;
            }

            var mean = values.Average();
            var variance = values.Sum(v => (v - mean) * (v - mean)) / (values.Count - 1);
            return variance;
        }

        private decimal Autocorrelation(List<decimal> values, int lag)
        {
            if (values.Count <= lag)
            {
                return 0m;
            }

            var mean = values.Average();
            var numerator = 0m;
            var denominator = 0m;
            for (var i = lag; i < values.Count; i++)
            {
                numerator += (values[i] - mean) * (values[i - lag] - mean);
            }

            foreach (var value in values)
            {
                denominator += (value - mean) * (value - mean);
            }

            return denominator == 0m ? 0m : numerator / denominator;
        }

        private decimal Skewness(List<decimal> values)
        {
            if (values.Count < 3)
            {
                return 0m;
            }

            var mean = values.Average();
            var m2 = values.Sum(v => (v - mean) * (v - mean)) / values.Count;
            var m3 = values.Sum(v => (v - mean) * (v - mean) * (v - mean)) / values.Count;
            if (m2 == 0m)
            {
                return 0m;
            }

            var skew = m3 / (decimal)Math.Pow((double)m2, 1.5);
            return skew;
        }

        private decimal Kurtosis(List<decimal> values)
        {
            if (values.Count < 4)
            {
                return 0m;
            }

            var mean = values.Average();
            var m2 = values.Sum(v => (v - mean) * (v - mean)) / values.Count;
            var m4 = values.Sum(v => (v - mean) * (v - mean) * (v - mean) * (v - mean)) / values.Count;
            if (m2 == 0m)
            {
                return 0m;
            }

            var kurt = m4 / (decimal)Math.Pow((double)m2, 2) - 3m;
            return kurt;
        }

        private decimal? ComputeNearestNode(List<decimal> values, bool high)
        {
            if (values.Count == 0)
            {
                return null;
            }

            var target = high ? values.Max() : values.Min();
            return target;
        }

        public void Export(Dictionary<string, object> data, DateTime time)
        {
            var directory = "C:\\ATASExport\\";
            lock (_fileLock)
            {
                Directory.CreateDirectory(directory);
                var dateFile = Path.Combine(directory, $"market_data_{time:yyyyMMdd}.json");
                AppendLine(dateFile, data);
                var latestFile = Path.Combine(directory, "latest.json");
                File.WriteAllText(latestFile, JsonConvert.SerializeObject(data, Formatting.Indented));
            }
        }

        private void AppendLine(string filePath, Dictionary<string, object> data)
        {
            var json = JsonConvert.SerializeObject(data, Formatting.None);
            using var stream = new FileStream(filePath, FileMode.Append, FileAccess.Write, FileShare.ReadWrite);
            using var writer = new StreamWriter(stream, Encoding.UTF8);
            writer.WriteLine(json);
        }

        private class SessionAggregator
        {
            private decimal _cumVolume;
            private decimal _cumVp;

            public decimal Vwap => _cumVolume == 0m ? 0m : _cumVp / _cumVolume;

            public void Add(decimal volume, decimal price)
            {
                _cumVolume += volume;
                _cumVp += volume * price;
            }
        }
    }
}
