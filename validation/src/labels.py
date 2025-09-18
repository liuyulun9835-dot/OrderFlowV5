"""Label generation for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class LabelArtifacts:
    forward_returns: pd.Series
    filters: pd.DataFrame
    meta_signals: pd.DataFrame
    primary_label: pd.Series


@dataclass
class LabelConfig:
    horizon: int = 12
    re_quantile: float = 0.7
    hv_quantile: float = 0.8
    hf_threshold: float = 0.8


def make_forward_returns(df: pd.DataFrame, column: str = "return", horizon: int = 12) -> pd.Series:
    returns = df[column].rolling(window=horizon).sum().shift(-horizon + 1)
    return returns.fillna(0.0)


def _build_filters(df: pd.DataFrame, config: LabelConfig) -> pd.DataFrame:
    re_threshold = df["return"].quantile(config.re_quantile)
    hv_threshold = df["vol_pctl"].quantile(config.hv_quantile)
    hf_threshold = float(np.quantile(np.abs(df["cvd_z"]), config.hf_threshold))

    filters = pd.DataFrame(index=df.index)
    filters["RE"] = (df["return"] >= re_threshold).astype(int)
    filters["HV"] = (df["vol_pctl"] >= hv_threshold).astype(int)
    filters["HF"] = (np.abs(df["cvd_z"]) >= hf_threshold).astype(int)
    return filters


def _build_meta_signals(filters: pd.DataFrame) -> pd.DataFrame:
    meta = pd.DataFrame(index=filters.index)
    meta["U1"] = ((filters["RE"] == 1) & (filters["HF"] == 1) & (filters["HV"] == 0)).astype(int)
    meta["U2"] = ((filters["RE"] == 1) & (filters["HF"] == 1)).astype(int)
    meta["U3"] = ((filters["RE"] == 1) & (filters["HV"] == 0)).astype(int)
    return meta


def make_labels(df: pd.DataFrame, config: LabelConfig | None = None) -> LabelArtifacts:
    config = config or LabelConfig()
    forward_returns = make_forward_returns(df, horizon=config.horizon)
    filters = _build_filters(df, config)
    meta_signals = _build_meta_signals(filters)
    primary_label = meta_signals["U2"].astype(int)
    return LabelArtifacts(
        forward_returns=forward_returns,
        filters=filters,
        meta_signals=meta_signals,
        primary_label=primary_label,
    )
