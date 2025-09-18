"""Quality control checks for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class QCReport:
    checks: Dict[str, bool]
    notes: Dict[str, str]

    def is_valid(self) -> bool:
        return all(self.checks.values())


def run_qc(
    df: pd.DataFrame,
    label_column: str,
    min_samples: int,
    stability_score: float,
    stability_threshold: float,
    required_states: tuple[str, ...] = ("BALANCED", "TRENDING", "TRANSITIONAL"),
) -> QCReport:
    checks: Dict[str, bool] = {}
    notes: Dict[str, str] = {}

    checks["sample_size"] = len(df) >= min_samples
    notes["sample_size"] = f"observations={len(df)}"

    checks["label_variance"] = df[label_column].nunique() > 1
    notes["label_variance"] = "ok" if checks["label_variance"] else "label column is constant"

    state_tags = set(df.get("state_tag", []))
    missing_states = [state for state in required_states if state not in state_tags]
    checks["state_coverage"] = not missing_states
    notes["state_coverage"] = "ok" if not missing_states else f"missing {missing_states}"

    checks["stability_threshold"] = stability_score >= stability_threshold
    notes["stability_threshold"] = f"score={stability_score:.2f}" if stability_score else "score unavailable"

    return QCReport(checks=checks, notes=notes)
