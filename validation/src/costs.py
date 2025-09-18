"""Cost sensitivity analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class CostScenario:
    name: str
    taker_fee_bps: float
    maker_fee_bps: float
    slippage_bps: float


def evaluate_costs(forward_returns: pd.Series, configs: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    """Return gross/net expectancy under different cost assumptions."""

    records = []
    gross = float(forward_returns.mean())
    volatility = float(forward_returns.std(ddof=1))
    sharpe = gross / volatility if volatility else 0.0
    hit_rate = float((forward_returns > 0).mean())

    for name, cfg in configs.items():
        taker_cost = cfg.get("taker_fee_bps", 0.0) / 10_000.0
        maker_cost = cfg.get("maker_fee_bps", 0.0) / 10_000.0
        slippage_cost = cfg.get("slippage_bps", 0.0) / 10_000.0
        total_cost = taker_cost + slippage_cost
        net = gross - total_cost
        records.append(
            {
                "scenario": name,
                "gross": gross,
                "net": net,
                "hit_rate": hit_rate,
                "sharpe": sharpe,
                "taker_fee_bps": cfg.get("taker_fee_bps", np.nan),
                "maker_fee_bps": cfg.get("maker_fee_bps", np.nan),
                "slippage_bps": cfg.get("slippage_bps", np.nan),
            }
        )

    return pd.DataFrame(records)
