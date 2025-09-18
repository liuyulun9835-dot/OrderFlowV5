"""Label generation for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pandas as pd


@dataclass
class LabelConfig:
    horizon: int = 12
    threshold: float = 0.0


def make_forward_returns(df: pd.DataFrame, column: str = "return", horizon: int = 12) -> pd.Series:
    return df[column].rolling(window=horizon).sum().shift(-horizon + 1)


def make_labels(df: pd.DataFrame, config: LabelConfig | None = None) -> Tuple[pd.Series, pd.Series]:
    config = config or LabelConfig()
    forward_returns = make_forward_returns(df, horizon=config.horizon)
    labels = (forward_returns > config.threshold).astype(int)
    return forward_returns.fillna(0.0), labels.fillna(0)
