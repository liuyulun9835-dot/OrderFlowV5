"""Trigger calculations used by the validator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class TriggerResult:
    scores: pd.Series
    threshold: float


def compute_trigger(df: pd.DataFrame, column: str, quantile: float = 0.9) -> TriggerResult:
    scores = df[column]
    threshold = float(scores.quantile(quantile))
    return TriggerResult(scores=scores, threshold=threshold)


def trigger_to_flags(trigger: TriggerResult) -> pd.Series:
    return (trigger.scores >= trigger.threshold).astype(int)


def build_trigger_matrix(df: pd.DataFrame, columns: Dict[str, float]) -> pd.DataFrame:
    data = {}
    for column, quantile in columns.items():
        trigger = compute_trigger(df, column, quantile)
        data[column] = trigger_to_flags(trigger)
    return pd.DataFrame(data)
