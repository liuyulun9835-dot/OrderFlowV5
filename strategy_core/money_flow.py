"""Money flow utilities using the standardised MFI field names."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from preprocessing.data_preprocessor import STANDARD_FIELDS


@dataclass
class MoneyFlowSignals:
    mfi: Mapping[str, float]

    def delta_pressure(self) -> float:
        return float(self.mfi.get("bar_delta") or 0.0)

    def cvd_momentum(self) -> float:
        fast = float(self.mfi.get("cvd_ema_fast") or 0.0)
        slow = float(self.mfi.get("cvd_ema_slow") or 1e-9)
        return fast - slow

    def imbalance_score(self) -> float:
        return float(self.mfi.get("imbalance") or 0.0)

    def z_score(self) -> float:
        return float(self.mfi.get("cvd_z") or 0.0)


def compute_money_flow(payload: Mapping[str, Mapping[str, float]]) -> Dict[str, float]:
    mfi = payload.get("MFI", {})
    missing = [field for field in STANDARD_FIELDS["MFI"] if field not in mfi]
    if missing:
        raise KeyError(f"MFI payload missing fields: {missing}")
    signals = MoneyFlowSignals(mfi)
    return {
        "delta_pressure": signals.delta_pressure(),
        "cvd_momentum": signals.cvd_momentum(),
        "imbalance_score": signals.imbalance_score(),
        "z_score": signals.z_score(),
    }
