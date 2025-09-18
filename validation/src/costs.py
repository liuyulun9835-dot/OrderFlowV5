"""Cost sensitivity analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class CostScenario:
    name: str
    taker_fee_bps: float
    maker_fee_bps: float
    slippage_bps: float


def evaluate_costs(base_pnl: pd.Series, configs: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    records = []
    gross = base_pnl.mean()
    for name, cfg in configs.items():
        total_cost = (cfg["taker_fee_bps"] + cfg["slippage_bps"]) / 10000.0
        net = gross - total_cost
        records.append({
            "scenario": name,
            "gross": gross,
            "net": net,
            "taker_fee_bps": cfg["taker_fee_bps"],
            "slippage_bps": cfg["slippage_bps"],
        })
    return pd.DataFrame(records)
