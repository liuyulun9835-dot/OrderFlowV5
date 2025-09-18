"""Utilities for enforcing standardized indicator field names.

This module centralizes the mapping between raw indicator payloads and the
canonical schema defined in the validator v2 documentation.  The goal is to
ensure every downstream component can rely on a consistent dictionary shape
for MSI, MFI, KLI and trade state fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping

STANDARD_FIELDS = {
    "MSI": [
        "poc",
        "vah",
        "val",
        "near_val",
        "near_vah",
        "near_poc",
        "value_migration",
        "value_migration_speed",
        "value_migration_consistency",
    ],
    "MFI": [
        "bar_delta",
        "cvd",
        "cvd_ema_fast",
        "cvd_ema_slow",
        "cvd_macd",
        "cvd_rsi",
        "cvd_z",
        "imbalance",
    ],
    "KLI": [
        "nearest_support",
        "nearest_resistance",
        "nearest_lvn",
        "nearest_hvn",
        "in_lvn",
        "absorption_detected",
        "absorption_strength",
        "absorption_side",
    ],
    "STATE": [
        "volume",
        "vol_pctl",
        "atr",
        "atr_norm_range",
        "keltner_pos",
        "vwap_session",
        "vwap_dev_bps",
        "ls_norm",
        "session_id",
        "state_tag",
        "state_confidence",
    ],
}


# Historical aliases that appeared in earlier notebooks / prototypes.  These
# mappings allow us to absorb legacy payloads without leaking non-compliant
# field names downstream.
LEGACY_ALIASES = {
    "MSI": {
        "point_of_control": "poc",
        "value_area_high": "vah",
        "value_area_low": "val",
        "near_value_area_low": "near_val",
        "near_value_area_high": "near_vah",
        "near_point_of_control": "near_poc",
        "value_shift": "value_migration",
        "value_shift_speed": "value_migration_speed",
        "value_shift_consistency": "value_migration_consistency",
    },
    "MFI": {
        "delta": "bar_delta",
        "cumulative_volume_delta": "cvd",
        "cvd_fast": "cvd_ema_fast",
        "cvd_slow": "cvd_ema_slow",
        "cvd_macd_hist": "cvd_macd",
        "cvd_relative_strength": "cvd_rsi",
        "large_z": "cvd_z",
        "imbalance_pct": "imbalance",
    },
    "KLI": {
        "support": "nearest_support",
        "resistance": "nearest_resistance",
        "lvn_distance": "nearest_lvn",
        "hvn_distance": "nearest_hvn",
        "is_in_lvn": "in_lvn",
        "absorption": "absorption_detected",
        "absorption_intensity": "absorption_strength",
        "absorption_direction": "absorption_side",
    },
    "STATE": {
        "vol": "volume",
        "volume_percentile": "vol_pctl",
        "average_true_range": "atr",
        "atr_range_norm": "atr_norm_range",
        "keltner_position": "keltner_pos",
        "session_vwap": "vwap_session",
        "vwap_deviation_bps": "vwap_dev_bps",
        "long_short_norm": "ls_norm",
        "session": "session_id",
        "tag": "state_tag",
        "confidence": "state_confidence",
    },
}


@dataclass
class IndicatorStandardizer:
    """Standardises indicator payloads according to the published schema."""

    schema: Mapping[str, Iterable[str]] = field(default_factory=lambda: STANDARD_FIELDS)
    aliases: Mapping[str, Mapping[str, str]] = field(default_factory=lambda: LEGACY_ALIASES)

    def _normalise_category(self, category: str, values: Mapping[str, Any]) -> Dict[str, Any]:
        allowed = set(self.schema[category])
        alias_map = self.aliases.get(category, {})
        cleaned: Dict[str, Any] = {field: None for field in allowed}
        for key, value in values.items():
            standard_key = alias_map.get(key, key)
            if standard_key not in allowed:
                raise KeyError(
                    f"Unknown field '{key}' for category {category}. "
                    "Please update preprocessing to match the indicator catalog."
                )
            cleaned[standard_key] = value
        return cleaned

    def transform(self, payload: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Return a new payload with aligned field names.

        The input is expected to contain MSI, MFI, KLI and STATE dictionaries.
        Missing categories are initialised with empty dictionaries so downstream
        code can rely on their presence.
        """

        transformed: Dict[str, Dict[str, Any]] = {}
        for category in self.schema.keys():
            category_payload = payload.get(category, {})
            transformed[category] = self._normalise_category(category, category_payload)
        return transformed


def standardise(payload: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convenience wrapper returning a fully standardised payload."""

    return IndicatorStandardizer().transform(payload)
