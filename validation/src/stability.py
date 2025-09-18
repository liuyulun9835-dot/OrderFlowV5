"""Rolling stability analysis for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

META_SIGNALS = ("U1", "U2", "U3")


@dataclass
class StabilityResult:
    metrics: pd.DataFrame
    score: float


def _stability(series: pd.Series, window: int = 90) -> float:
    if series.empty:
        return float("nan")
    window = min(window, len(series))
    if window < 10:
        window = max(5, len(series))
    rolling = series.rolling(window=window, min_periods=max(3, window // 3)).mean()
    return float((rolling >= 0.5).mean())


def compute_stability(
    df: pd.DataFrame,
    label_column: str,
    scene_column: str = "scene",
    meta_signals: Iterable[str] = META_SIGNALS,
) -> StabilityResult:
    records = []
    for scene, scene_df in df.groupby(scene_column):
        for meta in meta_signals:
            if meta not in scene_df:
                continue
            triggered = scene_df[scene_df[meta].astype(int) > 0]
            if triggered.empty:
                continue
            stability = _stability(triggered[label_column])
            records.append(
                {
                    "scene": scene,
                    "meta_signal": meta,
                    "stability": stability,
                    "N": len(triggered),
                }
            )

    metrics = pd.DataFrame(records)
    score = float(metrics["stability"].mean()) if not metrics.empty else 0.0
    return StabilityResult(metrics=metrics, score=score)
