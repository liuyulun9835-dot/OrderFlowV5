"""Multivariate models: Poisson/NegBin regression wrappers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd
import statsmodels.api as sm


@dataclass
class RegressionResult:
    params: pd.DataFrame
    model: str


def _fit_model(df: pd.DataFrame, label_column: str, family: sm.families.Family, name: str) -> RegressionResult:
    y = df[label_column]
    X = df.drop(columns=[label_column])
    X = sm.add_constant(X)
    model = sm.GLM(y, X, family=family)
    res = model.fit()
    params = res.summary2().tables[1]
    params.reset_index(inplace=True)
    params.rename(columns={"index": "variable"}, inplace=True)
    params["model"] = name
    return RegressionResult(params=params, model=name)


def run_regressions(df: pd.DataFrame, label_column: str) -> Dict[str, RegressionResult]:
    poisson = _fit_model(df, label_column, sm.families.Poisson(), "poisson")
    negbin = _fit_model(df, label_column, sm.families.NegativeBinomial(), "negative_binomial")
    return {
        poisson.model: poisson,
        negbin.model: negbin,
    }
