"""Market structure utilities using the standardised MSI field names."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from preprocessing.data_preprocessor import STANDARD_FIELDS


@dataclass
class MarketStructureSignals:
    """Derive market structure signals from MSI metrics."""

    msi: Mapping[str, float]

    def value_area_width(self) -> float:
        vah = self.msi.get("vah") or 0.0
        val = self.msi.get("val") or 0.0
        return float(vah) - float(val)

    def balance_status(self) -> str:
        migration = float(self.msi.get("value_migration") or 0.0)
        speed = float(self.msi.get("value_migration_speed") or 0.0)
        if abs(migration) < 1e-6:
            return "balanced"
        if migration > 0 and speed > 0:
            return "auction_up"
        if migration < 0 and speed < 0:
            return "auction_down"
        return "transition"


def compute_market_structure(payload: Mapping[str, Mapping[str, float]]) -> Dict[str, float | str]:
    msi = payload.get("MSI", {})
    missing = [field for field in STANDARD_FIELDS["MSI"] if field not in msi]
    if missing:
        raise KeyError(f"MSI payload missing fields: {missing}")
    signals = MarketStructureSignals(msi)
    return {
        "value_area_width": signals.value_area_width(),
        "balance_status": signals.balance_status(),
    }
