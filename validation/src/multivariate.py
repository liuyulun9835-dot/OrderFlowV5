"""Multivariate models for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import PerfectSeparationWarning
import warnings

warnings.filterwarnings("ignore", category=PerfectSeparationWarning)


@dataclass
class RegressionSummary:
    model: str
    params: pd.DataFrame
    dispersion: float | None = None


@dataclass
class MultivariateResult:
    combinations: pd.DataFrame
    state_breakdown: pd.DataFrame
    combo_matrix: pd.DataFrame
    frequency_model: RegressionSummary
    strength_model: RegressionSummary
    quantile_model: RegressionSummary


META_SIGNALS = ("U1", "U2", "U3")


def _design_matrix(df: pd.DataFrame, meta_signals: Iterable[str], controls: Iterable[str]) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    for meta in meta_signals:
        if meta in df:
            features[meta] = df[meta].astype(float)
    control_df = pd.get_dummies(df[list(controls)], drop_first=True, dtype=float)
    for column in control_df.columns:
        features[column] = control_df[column]
    features = sm.add_constant(features, has_constant="add")
    return features


def _fit_poisson_with_dispersion(X: pd.DataFrame, y: pd.Series) -> RegressionSummary:
    poisson_model = sm.GLM(y, X, family=sm.families.Poisson())
    poisson_res = poisson_model.fit()
    dispersion = poisson_res.deviance / poisson_res.df_resid if poisson_res.df_resid else None
    if dispersion and dispersion > 1.5:
        alpha = max(dispersion - 1, 1e-6)
        negbin_model = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=alpha))
        negbin_res = negbin_model.fit()
        params = negbin_res.summary2().tables[1].reset_index().rename(columns={"index": "variable"})
        return RegressionSummary(model="negative_binomial", params=params, dispersion=dispersion)
    params = poisson_res.summary2().tables[1].reset_index().rename(columns={"index": "variable"})
    return RegressionSummary(model="poisson", params=params, dispersion=dispersion)


def _fit_linear_model(X: pd.DataFrame, y: pd.Series, name: str) -> RegressionSummary:
    model = sm.OLS(y, X)
    res = model.fit()
    params = res.summary2().tables[1].reset_index().rename(columns={"index": "variable"})
    return RegressionSummary(model=name, params=params)


def _fit_quantile_model(X: pd.DataFrame, y: pd.Series, quantile: float = 0.5) -> RegressionSummary:
    model = sm.QuantReg(y, X)
    res = model.fit(q=quantile)
    params = res.params.to_frame(name="coef").reset_index().rename(columns={"index": "variable"})
    params["p_value"] = res.pvalues.reindex(params["variable"]).values
    params["model"] = f"quantile_{quantile:.2f}"
    return RegressionSummary(model=f"quantile_{quantile:.2f}", params=params)


def _summarise_combinations(
    meta_signals: Iterable[str],
    frequency: RegressionSummary,
    strength: RegressionSummary,
    quantile: RegressionSummary,
    df: pd.DataFrame,
    label_column: str,
) -> pd.DataFrame:
    rows: List[Dict[str, float]] = []
    freq_params = frequency.params.set_index("variable")["Coef." if "Coef." in frequency.params else "coef"]
    strength_params = strength.params.set_index("variable")["Coef." if "Coef." in strength.params else "coef"]
    quantile_params = quantile.params.set_index("variable")["coef"]

    for meta in meta_signals:
        if meta not in df:
            continue
        rows.append(
            {
                "meta_signal": meta,
                "frequency_model": frequency.model,
                "frequency_coef": freq_params.get(meta, np.nan),
                "strength_coef": strength_params.get(meta, np.nan),
                "quantile_coef": quantile_params.get(meta, np.nan),
                "q_rate": float(df[meta].mean()),
                "net_uplift": float(df.loc[df[meta] > 0, label_column].mean()),
            }
        )
    return pd.DataFrame(rows)


def _build_combo_matrix(df: pd.DataFrame, meta_signals: Iterable[str], label_column: str) -> pd.DataFrame:
    records = []
    for scene, scene_df in df.groupby("scene"):
        for meta in meta_signals:
            if meta not in scene_df:
                continue
            triggered = scene_df[scene_df[meta] > 0]
            N = len(triggered)
            hit_rate = float(triggered[label_column].mean()) if N else np.nan
            records.append(
                {
                    "scene": scene,
                    "meta_signal": meta,
                    "N": N,
                    "hit_rate": hit_rate,
                }
            )
    return pd.DataFrame(records)


def _state_breakdown(df: pd.DataFrame, meta_signals: Iterable[str], label_column: str) -> pd.DataFrame:
    records = []
    for state, state_df in df.groupby("state_tag"):
        for meta in meta_signals:
            if meta not in state_df:
                continue
            triggered = state_df[state_df[meta] > 0]
            N = len(triggered)
            hit_rate = float(triggered[label_column].mean()) if N else np.nan
            records.append({"state_tag": state, "meta_signal": meta, "N": N, "hit_rate": hit_rate})
    return pd.DataFrame(records)


def run_regressions(
    df: pd.DataFrame,
    label_column: str,
    forward_returns: pd.Series,
    controls: Iterable[str],
    meta_signals: Iterable[str] = META_SIGNALS,
) -> MultivariateResult:
    meta_signals = tuple(meta_signals)
    controls = tuple(controls)

    X_freq = _design_matrix(df, meta_signals, controls)
    y_freq = df[label_column].astype(float)
    frequency_model = _fit_poisson_with_dispersion(X_freq, y_freq)

    X_strength = X_freq
    y_strength = forward_returns.loc[X_strength.index].astype(float)
    strength_model = _fit_linear_model(X_strength, y_strength, name="ols")
    quantile_model = _fit_quantile_model(X_strength, y_strength, quantile=0.5)

    combinations = _summarise_combinations(meta_signals, frequency_model, strength_model, quantile_model, df, label_column)
    combo_matrix = _build_combo_matrix(df, meta_signals, label_column)
    state_breakdown = _state_breakdown(df, meta_signals, label_column)

    return MultivariateResult(
        combinations=combinations,
        state_breakdown=state_breakdown,
        combo_matrix=combo_matrix,
        frequency_model=frequency_model,
        strength_model=strength_model,
        quantile_model=quantile_model,
    )
