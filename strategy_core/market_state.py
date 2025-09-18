"""Market state calculation utilities aligned with the indicator schema."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from preprocessing.data_preprocessor import STANDARD_FIELDS


@dataclass
class MarketState:
    state: Mapping[str, float]

    def compute_confidence(self) -> float:
        volume = float(self.state.get("volume") or 0.0)
        atr = float(self.state.get("atr") or 1.0)
        ls_norm = float(self.state.get("ls_norm") or 0.0)
        raw_confidence = min(1.0, volume / (atr * 10.0))
        adjusted = max(0.0, min(1.0, raw_confidence - abs(ls_norm) * 0.05))
        return round(adjusted, 4)

    def to_dict(self) -> Dict[str, float | str]:
        data = {field: self.state.get(field) for field in STANDARD_FIELDS["STATE"] if field != "state_confidence"}
        data["state_confidence"] = self.state.get("state_confidence", self.compute_confidence())
        return data


def compute_market_state(payload: Mapping[str, Mapping[str, float]]) -> Dict[str, float | str]:
    state = payload.get("STATE", {})
    missing = [field for field in STANDARD_FIELDS["STATE"] if field not in state and field != "state_confidence"]
    if missing:
        raise KeyError(f"STATE payload missing fields: {missing}")
    market_state = MarketState(state)
    return market_state.to_dict()
