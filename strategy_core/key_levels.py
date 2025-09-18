"""Key level indicators built from the standardised KLI field names."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from preprocessing.data_preprocessor import STANDARD_FIELDS


@dataclass
class KeyLevelSignals:
    kli: Mapping[str, float]

    def nearest_levels(self) -> Dict[str, float]:
        return {
            "nearest_support": float(self.kli.get("nearest_support") or 0.0),
            "nearest_resistance": float(self.kli.get("nearest_resistance") or 0.0),
            "nearest_lvn": float(self.kli.get("nearest_lvn") or 0.0),
            "nearest_hvn": float(self.kli.get("nearest_hvn") or 0.0),
        }

    def absorption_flags(self) -> Dict[str, float | str]:
        return {
            "in_lvn": bool(self.kli.get("in_lvn")),
            "absorption_detected": bool(self.kli.get("absorption_detected")),
            "absorption_strength": float(self.kli.get("absorption_strength") or 0.0),
            "absorption_side": self.kli.get("absorption_side") or "none",
        }


def compute_key_levels(payload: Mapping[str, Mapping[str, float]]) -> Dict[str, float | str | bool]:
    kli = payload.get("KLI", {})
    missing = [field for field in STANDARD_FIELDS["KLI"] if field not in kli]
    if missing:
        raise KeyError(f"KLI payload missing fields: {missing}")
    signals = KeyLevelSignals(kli)
    data: Dict[str, float | str | bool] = {}
    data.update(signals.nearest_levels())
    data.update(signals.absorption_flags())
    return data
