"""Rolling stability analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class StabilityResult:
    metrics: pd.DataFrame
    score: float


def compute_stability(df: pd.DataFrame, label_column: str, window: int = 50) -> StabilityResult:
    rolling_mean = df[label_column].rolling(window=window).mean().dropna()
    stability = float((rolling_mean > 0).mean())
    metrics = pd.DataFrame({
        "rolling_mean": rolling_mean,
        "window": window,
    })
    return StabilityResult(metrics=metrics, score=stability)
