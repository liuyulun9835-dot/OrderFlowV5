import argparse
import csv
import os
import time
from datetime import datetime, timezone
from typing import Iterable, List

import requests

BASE_URL = "https://api.binance.com/api/v3/klines"
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_INTERVAL = "1m"
EXPORT_PATH = "./data/binance_klines/"
MAX_LIMIT = 1000

INTERVAL_TO_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
}


def interval_to_milliseconds(interval: str) -> int:
    if interval not in INTERVAL_TO_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_TO_MS[interval]


def build_params(symbol: str, interval: str, start_ms: int, end_ms: int) -> dict:
    return {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": MAX_LIMIT,
    }


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> List[List]:
    params = build_params(symbol, interval, start_ms, end_ms)
    response = requests.get(BASE_URL, params=params, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Binance API error {response.status_code}: {response.text}")
    return response.json()


def ensure_export_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_existing_end(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as handle:
        last_line = None
        for last_line in handle:
            pass
    if not last_line:
        return 0
    last_timestamp = int(last_line.split(",", 1)[0])
    return last_timestamp + 1


def write_rows(path: str, rows: Iterable[List]) -> None:
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if write_header:
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for row in rows:
            writer.writerow(row)


def kline_to_row(kline: List, interval_ms: int) -> List:
    open_time = int(kline[0])
    close_time = int(kline[6])
    timestamp = close_time - interval_ms // 2
    return [
        timestamp,
        float(kline[1]),
        float(kline[2]),
        float(kline[3]),
        float(kline[4]),
        float(kline[5]),
    ]


def daterange_to_ms(start: datetime, end: datetime) -> List[int]:
    return [int(start.timestamp() * 1000), int(end.timestamp() * 1000)]


def download(symbol: str, interval: str, start: datetime, end: datetime, export_dir: str) -> None:
    ensure_export_dir(export_dir)
    export_path = os.path.join(export_dir, f"{symbol}_{interval}.csv")
    interval_ms = interval_to_milliseconds(interval)
    start_ms, end_ms = daterange_to_ms(start, end)
    cursor = max(start_ms, get_existing_end(export_path))

    while cursor < end_ms:
        batch_end = min(cursor + interval_ms * MAX_LIMIT, end_ms)
        try:
            klines = fetch_klines(symbol, interval, cursor, batch_end)
        except RuntimeError as exc:
            print(f"Error fetching data: {exc}. Retrying in 5 seconds...")
            time.sleep(5)
            continue

        if not klines:
            cursor += interval_ms * MAX_LIMIT
            continue

        rows = [kline_to_row(kline, interval_ms) for kline in klines]
        write_rows(export_path, rows)
        cursor = klines[-1][6] + 1
        time.sleep(0.5)

    print(f"Download complete: {export_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Binance historical klines with resume support")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Trading pair symbol (default BTCUSDT)")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="Kline interval (1m,5m,15m,30m,1h)")
    parser.add_argument("--start", default="2017-12-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default=EXPORT_PATH, help="Export directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end <= start:
        raise ValueError("End date must be after start date")
    download(args.symbol.upper(), args.interval, start, end, args.output)


if __name__ == "__main__":
    main()
