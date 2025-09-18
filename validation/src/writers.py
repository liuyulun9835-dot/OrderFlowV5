"""Writers for validator outputs."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd


def ensure_results_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _excel_path(results_dir: Path) -> Path:
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return results_dir / f"OF_V5_stats_{stamp}.xlsx"


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


def build_rule_sheet(univariate: pd.DataFrame, whitelist: Iterable[str]) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    whitelist = set(whitelist)
    passed = univariate[univariate["passes_threshold"]]
    for _, row in passed.iterrows():
        if row["scene"] not in whitelist:
            continue
        rows.append(
            {
                "scene": row["scene"],
                "filter": row["filter"],
                "meta_signal": row["meta_signal"],
                "metric": row["metric"],
                "N": row["N"],
                "hit_rate": row["hit_rate"],
                "uplift": row["uplift"],
                "p_adjusted": row.get("p_adjusted"),
            }
        )
    return pd.DataFrame(rows)


def make_scene_lists(univariate: pd.DataFrame, whitelist_reference: Iterable[str]) -> Tuple[List[str], List[str]]:
    whitelist_reference = list(whitelist_reference)
    passed = univariate[univariate["passes_threshold"]]["scene"].unique().tolist()
    whitelist = [scene for scene in whitelist_reference if scene in passed]
    blacklist = [scene for scene in whitelist_reference if scene not in whitelist]
    return whitelist, blacklist


def write_outputs(
    results_dir: Path,
    univariate: pd.DataFrame,
    combinations: pd.DataFrame,
    state_breakdown: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    whitelist: List[str],
    blacklist: List[str],
    combo_matrix: pd.DataFrame,
    qc_summary: Dict[str, str],
) -> Dict[str, Path]:
    ensure_results_dir(results_dir)
    excel_path = _excel_path(results_dir)
    parquet_path = results_dir / "combo_matrix.parquet"
    json_path = results_dir / "white_black_list.json"
    report_path = results_dir / "validator_v2_report.md"

    rule_sheet = build_rule_sheet(univariate, whitelist)
    sheets = {
        "univariate": univariate,
        "combinations": combinations,
        "state_breakdown": state_breakdown,
        "cost_sensitivity": cost_sensitivity,
        "rules_white_list": rule_sheet,
    }
    write_excel(excel_path, sheets)

    write_parquet(parquet_path, combo_matrix)

    payload = {"whitelist": whitelist, "blacklist": blacklist}
    write_json(json_path, payload)

    summary_lines = [f"- {key}: {value}" for key, value in qc_summary.items()]
    write_markdown(report_path, {"Validator v2": "\n".join(summary_lines)})

    return {
        "excel": excel_path,
        "parquet": parquet_path,
        "json": json_path,
        "markdown": report_path,
    }
