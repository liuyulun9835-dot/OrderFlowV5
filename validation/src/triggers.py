"""Trigger calculations used by the validator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

import pandas as pd


@dataclass
class TriggerSummary:
    thresholds: Dict[str, float]
    matrix: pd.DataFrame


def build_trigger_matrix(df: pd.DataFrame, columns: Iterable[str], quantile: float = 0.9) -> TriggerSummary:
    """Create a boolean trigger matrix using quantile thresholds."""

    thresholds: Dict[str, float] = {}
    matrix = pd.DataFrame(index=df.index)
    for column in columns:
        if column not in df:
            continue
        threshold = float(df[column].quantile(quantile))
        matrix[column] = (df[column] >= threshold).astype(int)
        thresholds[column] = threshold
    return TriggerSummary(thresholds=thresholds, matrix=matrix)
