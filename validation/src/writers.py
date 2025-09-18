"""Writers for validator outputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


def ensure_results_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_excel(path: Path, sheets: Dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path) as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)


def write_parquet(path: Path, df: pd.DataFrame) -> None:
    df.to_parquet(path, index=False)


def write_json(path: Path, payload: Dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_markdown(path: Path, sections: Dict[str, str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for title, content in sections.items():
            handle.write(f"# {title}\n\n{content}\n\n")


def sync_trade_rules(config_path: Path, rules: Dict[str, list]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(rules, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
