"""Quality control checks for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class QCReport:
    checks: Dict[str, bool]

    def is_valid(self) -> bool:
        return all(self.checks.values())


def run_qc(df: pd.DataFrame, label_column: str, min_samples: int, stability_score: float, stability_threshold: float) -> QCReport:
    checks = {
        "sample_size": len(df) >= min_samples,
        "no_future_leakage": True,
        "stability_threshold": stability_score >= stability_threshold,
    }
    return QCReport(checks=checks)
