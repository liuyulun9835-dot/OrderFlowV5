import argparse
import glob
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import yaml
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

CONFIG_PATH = "validator_config.yaml"
ATAS_DATA_PATH = "./data/atas/"
BINANCE_DATA_PATH = "./data/binance_klines/"
RESULTS_DIR = "results"
ROLLING_WINDOW_DAYS = 90
THRESHOLD_SENSITIVITY = 0.1


class ValidationError(Exception):
    """Custom error for validation workflow."""


def load_config(path: str) -> Dict:
    if not os.path.exists(path):
        raise ValidationError(f"Configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as cfg:
        return yaml.safe_load(cfg) or {}


def load_indicator_files(path: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(path, "*.json")))
    if not files:
        raise ValidationError(f"No indicator files found in {path}")

    records: List[Dict] = []
    for file in files:
        with open(file, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = json.loads(handle.read())
                records.append(payload)

    df = pd.DataFrame(records)
    if "timestamp" not in df.columns:
        raise ValidationError("Indicator data must include a timestamp column")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    df = df.set_index("timestamp")
    return df


def load_binance_data(path: str) -> pd.DataFrame:
    csv_files = sorted(glob.glob(os.path.join(path, "*.csv")))
    if not csv_files:
        raise ValidationError(f"No Binance CSV files found in {path}")

    frames: List[pd.DataFrame] = []
    for file in csv_files:
        frame = pd.read_csv(file)
        if "timestamp" not in frame.columns:
            raise ValidationError(f"CSV missing timestamp column: {file}")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frames.append(frame)

    data = pd.concat(frames).sort_values("timestamp").drop_duplicates("timestamp")
    data = data.set_index("timestamp")
    return data


def compute_future_returns(prices: pd.Series, horizons: Iterable[int]) -> pd.DataFrame:
    future_returns = {}
    for horizon in horizons:
        delta = prices.shift(-horizon) / prices - 1.0
        future_returns[f"fut_ret_{horizon}m"] = delta
    return pd.DataFrame(future_returns)


def apply_slice(df: pd.DataFrame, condition: str) -> pd.DataFrame:
    if not condition:
        return df
    try:
        return df.query(condition)
    except Exception as exc:
        raise ValidationError(f"Failed to evaluate slice condition '{condition}': {exc}")


def run_t_test(data: pd.Series) -> Tuple[float, float]:
    data = data.dropna()
    if data.empty:
        return float("nan"), float("nan")
    stat, p_value = stats.ttest_1samp(data, 0.0, nan_policy="omit")
    return float(stat), float(p_value)


def run_bootstrap(data: pd.Series, n_iter: int = 1000) -> Tuple[float, Tuple[float, float]]:
    data = data.dropna().to_numpy()
    if data.size == 0:
        return float("nan"), (float("nan"), float("nan"))
    rng = np.random.default_rng(1234)
    means = []
    for _ in range(n_iter):
        sample = rng.choice(data, size=data.size, replace=True)
        means.append(sample.mean())
    mean = float(np.mean(means))
    lower, upper = np.percentile(means, [2.5, 97.5])
    return mean, (float(lower), float(upper))


def run_spearman(x: pd.Series, y: pd.Series) -> Tuple[float, float]:
    valid = x.notna() & y.notna()
    if valid.sum() == 0:
        return float("nan"), float("nan")
    corr, p_value = stats.spearmanr(x[valid], y[valid])
    return float(corr), float(p_value)


def run_logistic_regression(feature: pd.Series, target: pd.Series) -> Tuple[float, float]:
    valid = feature.notna() & target.notna()
    if valid.sum() < 20:
        return float("nan"), float("nan")
    x = feature[valid].to_numpy().reshape(-1, 1)
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)
    y = (target[valid] > 0).astype(int)
    model = LogisticRegression(max_iter=1000)
    model.fit(x_scaled, y)
    coef = float(model.coef_[0][0])
    pred = model.predict_proba(x_scaled)[:, 1]
    _, p_value = stats.ttest_1samp(pred - y, 0.0, nan_policy="omit")
    return coef, float(p_value)


def benjamini_hochberg(p_values: List[float]) -> List[float]:
    n = len(p_values)
    if n == 0:
        return []
    sorted_indices = np.argsort(p_values)
    adjusted = np.full(n, np.nan)
    cum_min = 1.0
    for rank, idx in enumerate(sorted_indices, start=1):
        p_adj = p_values[idx] * n / rank
        cum_min = min(cum_min, p_adj)
        adjusted[idx] = cum_min
    return adjusted.tolist()


def rolling_window_stability(series: pd.Series, window: timedelta) -> float:
    if series.empty:
        return float("nan")
    wins = 0
    total = 0
    start = series.index.min()
    end = series.index.max()
    current = start
    while current < end:
        segment = series.loc[current: current + window]
        if segment.dropna().empty:
            current += window
            continue
        sign = np.sign(segment.dropna().mean())
        if sign != 0:
            wins += np.mean(np.sign(segment.dropna()) == sign)
            total += 1
        current += window
    if total == 0:
        return float("nan")
    return wins / total


def threshold_sensitivity(series: pd.Series, base_threshold: float) -> float:
    if base_threshold == 0:
        return float("nan")
    perturbations = [1 - THRESHOLD_SENSITIVITY, 1 + THRESHOLD_SENSITIVITY]
    base_signal = (series > base_threshold).mean()
    deviations = []
    for factor in perturbations:
        perturbed = (series > base_threshold * factor).mean()
        deviations.append(abs(perturbed - base_signal))
    return float(np.mean(deviations))


def ensure_results_dir() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate ATAS indicator exports against Binance data")
    parser.add_argument("--atas", default=ATAS_DATA_PATH, help="Path to ATAS JSON exports")
    parser.add_argument("--binance", default=BINANCE_DATA_PATH, help="Path to Binance CSV data")
    parser.add_argument("--config", default=CONFIG_PATH, help="Validator configuration file")
    args = parser.parse_args()

    config = load_config(args.config)
    indicator_data = load_indicator_files(args.atas)
    binance_data = load_binance_data(args.binance)

    combined = indicator_data.join(binance_data, how="inner", rsuffix="_binance")
    if combined.empty:
        raise ValidationError("Combined dataset is empty after joining indicator and Binance data")

    horizons = config.get("horizons", [5, 15, 30, 60])
    future_returns = compute_future_returns(combined["close"], horizons)
    dataset = combined.join(future_returns)

    results_rows: List[Dict] = []
    p_values: List[float] = []

    slices = config.get("slices", []) or [{"name": "all", "condition": None}]
    tests = config.get("tests", ["t-test", "spearman_corr"])

    indicators = config.get("indicators", [])
    if not indicators:
        indicators = [{"name": col} for col in indicator_data.columns]

    ensure_results_dir()

    for indicator_cfg in indicators:
        indicator_name = indicator_cfg.get("name")
        if indicator_name not in dataset.columns:
            continue
        indicator_series = dataset[indicator_name]
        threshold = indicator_cfg.get("threshold")

        for slice_cfg in indicator_cfg.get("slices", slices):
            slice_name = slice_cfg.get("name", "all")
            condition = slice_cfg.get("condition")
            sliced = apply_slice(dataset, condition)
            if sliced.empty:
                continue

            for horizon in indicator_cfg.get("horizons", horizons):
                horizon_key = f"fut_ret_{horizon}m"
                if horizon_key not in sliced.columns:
                    continue
                future = sliced[horizon_key]
                if future.dropna().empty:
                    continue

                stats_summary: Dict[str, object] = {
                    "indicator": indicator_name,
                    "slice": slice_name,
                    "horizon": horizon_key,
                    "mean_ret": float(future.mean()),
                    "win_rate": float((future > 0).mean()),
                    "sample_size": int(future.dropna().shape[0])
                }

                effect_size = float(indicator_series.loc[sliced.index].mean())
                stats_summary["effect_size"] = effect_size

                for test in indicator_cfg.get("tests", tests):
                    if test == "t-test":
                        stat, p_value = run_t_test(future)
                        stats_summary["t_stat"] = stat
                        stats_summary["p_value"] = p_value
                    elif test == "bootstrap":
                        mean, (ci_low, ci_high) = run_bootstrap(future)
                        stats_summary["bootstrap_mean"] = mean
                        stats_summary["ci_low"] = ci_low
                        stats_summary["ci_high"] = ci_high
                    elif test == "spearman_corr":
                        corr, p_value = run_spearman(indicator_series.loc[sliced.index], future)
                        stats_summary["spearman_corr"] = corr
                        stats_summary["p_value"] = p_value
                    elif test == "logistic_regression":
                        coef, p_value = run_logistic_regression(indicator_series.loc[sliced.index], future)
                        stats_summary["logit_coef"] = coef
                        stats_summary["p_value"] = p_value

                if "p_value" in stats_summary and not np.isnan(stats_summary["p_value"]):
                    p_values.append(stats_summary["p_value"])

                if threshold is not None:
                    stats_summary["threshold_sensitivity"] = threshold_sensitivity(indicator_series, float(threshold))

                stability = rolling_window_stability(future.dropna(), timedelta(days=ROLLING_WINDOW_DAYS))
                stats_summary["rolling_stability"] = stability

                results_rows.append(stats_summary)

    if results_rows:
        adjusted = benjamini_hochberg([row.get("p_value", np.nan) for row in results_rows])
        for row, padj in zip(results_rows, adjusted):
            row["p_adj"] = padj

    report = pd.DataFrame(results_rows)
    csv_path = os.path.join(RESULTS_DIR, "validation_report.csv")
    excel_path = os.path.join(RESULTS_DIR, "validation_report.xlsx")
    report.to_csv(csv_path, index=False)
    with pd.ExcelWriter(excel_path) as writer:
        report.to_excel(writer, index=False)

    print(f"Validation completed. Results saved to {csv_path} and {excel_path}.")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as error:
        print(f"Validation failed: {error}")
        raise
