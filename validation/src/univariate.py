"""Univariate statistical checks with scene/filter/meta-signal gating."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.weightstats import ttest_ind


DEFAULT_FILTERS = ("RE", "HV", "HF")
DEFAULT_META_SIGNALS = ("U1", "U2", "U3")


@dataclass
class UnivariateConfig:
    metrics: Iterable[str]
    min_samples: int
    fdr_alpha: float
    stability_threshold: float
    scene_column: str = "scene"
    filters: Iterable[str] = field(default_factory=lambda: DEFAULT_FILTERS)
    meta_signals: Iterable[str] = field(default_factory=lambda: DEFAULT_META_SIGNALS)


@dataclass
class UnivariateResult:
    summary: pd.DataFrame
    config: UnivariateConfig


def _stability_score(series: pd.Series, window: int = 50) -> float:
    if series.empty:
        return float("nan")
    window = min(window, len(series))
    if window < 5:
        window = 5
    rolling = series.rolling(window=window, min_periods=max(3, window // 2)).mean()
    return float((rolling >= 0.5).mean())


def _ensure_boolean(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(int) > 0


def compute_univariate(df: pd.DataFrame, label_column: str, config: UnivariateConfig) -> UnivariateResult:
    records: List[dict] = []
    metrics = list(config.metrics)
    label_series = df[label_column]
    if label_series.sum() < 1:
        raise ValueError("Label column has no positive samples")

    for scene, scene_df in df.groupby(config.scene_column):
        for filter_name in config.filters:
            if filter_name not in scene_df:
                continue
            filter_series = _ensure_boolean(scene_df[filter_name])
            filter_rate = float(filter_series.mean())
            for meta_signal in config.meta_signals:
                if meta_signal not in scene_df:
                    continue
                mask = _ensure_boolean(scene_df[meta_signal])
                subset = scene_df[mask]
                N = int(len(subset))
                if N == 0:
                    continue
                y = subset[label_column]
                if y.nunique() < 2:
                    continue
                stability = _stability_score(y)
                hit_rate = float(y.mean())
                for metric in metrics:
                    if metric not in subset:
                        continue
                    values = subset[metric].astype(float)
                    pos = values[y == 1]
                    neg = values[y == 0]
                    if len(pos) < 5 or len(neg) < 5:
                        continue
                    stat, p_value, _ = ttest_ind(pos, neg, usevar="unequal")
                    p_value = float(np.clip(p_value, 0.0, 1.0))
                    uplift = float(pos.mean() - neg.mean())
                    records.append(
                        {
                            "scene": scene,
                            "filter": filter_name,
                            "meta_signal": meta_signal,
                            "metric": metric,
                            "N": N,
                            "filter_rate": filter_rate,
                            "hit_rate": hit_rate,
                            "uplift": uplift,
                            "t_stat": float(stat),
                            "p_value": p_value,
                            "stability": stability,
                        }
                    )

    columns = [
        "scene",
        "filter",
        "meta_signal",
        "metric",
        "N",
        "filter_rate",
        "hit_rate",
        "uplift",
        "t_stat",
        "p_value",
        "stability",
    ]
    if records:
        summary = pd.DataFrame(records, columns=columns)
        reject, p_adj, _, _ = multipletests(summary["p_value"], alpha=config.fdr_alpha, method="fdr_bh")
        summary["p_adjusted"] = p_adj
        summary["reject"] = reject
        summary["passes_threshold"] = (
            (summary["N"] >= config.min_samples)
            & summary["reject"]
            & (summary["stability"] >= config.stability_threshold)
        )
    else:
        summary = pd.DataFrame(columns=columns + ["p_adjusted", "reject", "passes_threshold"])

    summary["fdr_alpha"] = config.fdr_alpha
    return UnivariateResult(summary=summary.sort_values(["scene", "metric"]).reset_index(drop=True), config=config)
