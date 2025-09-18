"""Univariate statistical checks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests


@dataclass
class UnivariateResult:
    summary: pd.DataFrame
    fdr_alpha: float


def compute_univariate(df: pd.DataFrame, label_column: str, fdr_alpha: float) -> UnivariateResult:
    numeric_df = df.select_dtypes(include=["number"])
    metrics = [col for col in numeric_df.columns if col != label_column]
    df = numeric_df
    records = []
    labels = df[label_column]
    if labels.sum() < 1:
        raise ValueError("Label column has no positive samples")
    for column in metrics:
        correlation = float(np.corrcoef(df[column], labels)[0, 1])
        p_value = float(1.0 - abs(correlation)) / 2.0
        records.append({
            "metric": column,
            "correlation": correlation,
            "p_value": p_value,
        })
    summary = pd.DataFrame(records)
    reject, p_adj, _, _ = multipletests(summary["p_value"], alpha=fdr_alpha, method="fdr_bh")
    summary["p_adjusted"] = p_adj
    summary["reject"] = reject
    summary["fdr_alpha"] = fdr_alpha
    return UnivariateResult(summary=summary.sort_values("p_adjusted"), fdr_alpha=fdr_alpha)
