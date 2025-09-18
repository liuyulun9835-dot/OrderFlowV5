"""Data loading utilities for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from preprocessing.data_preprocessor import STANDARD_FIELDS, standardise

STATE_TAGS = ("BALANCED", "TRENDING", "TRANSITIONAL")
SESSION_IDS = ("asia", "eu", "us")


def _numeric_series(rng: np.random.Generator, size: int, loc: float = 0.0, scale: float = 1.0) -> np.ndarray:
    return rng.normal(loc=loc, scale=scale, size=size)


def _bounded_uniform(rng: np.random.Generator, size: int, low: float = 0.0, high: float = 1.0) -> np.ndarray:
    return rng.uniform(low=low, high=high, size=size)


def _choice(rng: np.random.Generator, options: Iterable, size: int) -> np.ndarray:
    options = tuple(options)
    return rng.choice(options, size=size)


def _generate_indicator_frame(size: int = 1_200) -> pd.DataFrame:
    """Generate a synthetic but schema-compliant indicator dataset."""

    rng = np.random.default_rng(seed=7)
    data: Dict[str, np.ndarray] = {}

    # Market structure (MSI)
    data["poc"] = _numeric_series(rng, size, loc=100.0, scale=2.5)
    data["vah"] = data["poc"] + np.abs(_numeric_series(rng, size, scale=1.5))
    data["val"] = data["poc"] - np.abs(_numeric_series(rng, size, scale=1.5))
    for field in ("near_val", "near_vah", "near_poc"):
        data[field] = rng.integers(0, 2, size=size)
    data["value_migration"] = _choice(rng, ("UP", "DOWN", "FLAT"), size)
    data["value_migration_speed"] = _numeric_series(rng, size, scale=0.05)
    data["value_migration_consistency"] = _bounded_uniform(rng, size)

    # Money flow (MFI)
    data["bar_delta"] = _numeric_series(rng, size, scale=50.0)
    data["cvd"] = rng.standard_normal(size=size).cumsum()
    data["cvd_ema_fast"] = _numeric_series(rng, size, scale=15.0)
    data["cvd_ema_slow"] = _numeric_series(rng, size, scale=10.0)
    data["cvd_macd"] = data["cvd_ema_fast"] - data["cvd_ema_slow"]
    data["cvd_rsi"] = _bounded_uniform(rng, size)
    data["cvd_z"] = _numeric_series(rng, size)
    data["imbalance"] = _bounded_uniform(rng, size, low=-1.0, high=1.0)

    # Key levels (KLI)
    data["nearest_support"] = data["val"] - np.abs(_numeric_series(rng, size, scale=1.0))
    data["nearest_resistance"] = data["vah"] + np.abs(_numeric_series(rng, size, scale=1.0))
    data["nearest_lvn"] = np.abs(_numeric_series(rng, size, scale=0.8))
    data["nearest_hvn"] = np.abs(_numeric_series(rng, size, scale=0.8))
    data["in_lvn"] = rng.integers(0, 2, size=size)
    data["absorption_detected"] = rng.integers(0, 2, size=size)
    data["absorption_strength"] = _bounded_uniform(rng, size)
    data["absorption_side"] = _choice(rng, ("bid", "ask"), size)

    # Volume and momentum / positioning
    data["volume"] = np.abs(_numeric_series(rng, size, loc=5_000.0, scale=1_000.0))
    data["vol_pctl"] = _bounded_uniform(rng, size)
    data["atr"] = np.abs(_numeric_series(rng, size, loc=1.0, scale=0.2))
    data["atr_norm_range"] = np.abs(_numeric_series(rng, size, loc=1.2, scale=0.3))
    data["keltner_pos"] = _bounded_uniform(rng, size, low=-1.0, high=1.0)
    data["vwap_session"] = _numeric_series(rng, size, loc=100.0, scale=2.0)
    data["vwap_dev_bps"] = _numeric_series(rng, size, scale=5.0)

    # Liquidity / session
    data["ls_norm"] = _bounded_uniform(rng, size)
    data["session_id"] = _choice(rng, SESSION_IDS, size)

    # Market state
    data["state_tag"] = _choice(rng, STATE_TAGS, size)
    data["state_confidence"] = _bounded_uniform(rng, size)

    # Additional controls used by validation
    data["spread_bps"] = _bounded_uniform(rng, size, low=0.5, high=3.0)
    data["return"] = _numeric_series(rng, size, loc=0.02, scale=0.15)

    # Scene gating
    whitelist = tuple(_scene_whitelist())
    data["scene"] = _choice(rng, whitelist, size)

    frame = pd.DataFrame(data)
    return frame


def _scene_whitelist() -> Iterable[str]:
    from pathlib import Path
    import yaml

    config_path = Path("validation/configs/scenes_whitelist.yaml")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        scenes = payload.get("scenes", [])
        if scenes:
            return scenes
    return [f"SCENE_{idx:03d}" for idx in range(1, 21)]


def _to_payload(record: pd.Series) -> Dict[str, Dict[str, float]]:
    payload: Dict[str, Dict[str, float]] = {}
    for category, fields in STANDARD_FIELDS.items():
        payload[category] = {field: record[field] for field in fields}
    return standardise(payload)


@dataclass
class DatasetBundle:
    frame: pd.DataFrame
    payloads: List[Dict[str, Dict[str, float]]]


def load_dataset(size: int = 1_200) -> Tuple[pd.DataFrame, List[Dict[str, Dict[str, float]]]]:
    """Return a synthetic dataset and standardised payload list."""

    frame = _generate_indicator_frame(size)
    payloads = [_to_payload(frame.iloc[i]) for i in range(len(frame))]
    return frame, payloads
