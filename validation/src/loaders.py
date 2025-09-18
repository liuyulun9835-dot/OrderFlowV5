"""Data loading utilities for validator v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from preprocessing.data_preprocessor import STANDARD_FIELDS, standardise


@dataclass
class IndicatorData:
    frames: Dict[str, pd.DataFrame]


def _generate_synthetic_category(name: str, size: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42 + hash(name) % 1_000_000)
    columns = STANDARD_FIELDS[name]
    data = {col: rng.normal(loc=0.0, scale=1.0, size=size) for col in columns}
    if name == "STATE":
        data["state_tag"] = rng.choice(["trend", "range", "vol_crush"], size=size)
        data["session_id"] = rng.integers(1, 5, size=size)
        data["state_confidence"] = np.clip(rng.normal(0.7, 0.1, size=size), 0.0, 1.0)
    return pd.DataFrame(data)


def load_indicator_frames(size: int = 400) -> IndicatorData:
    frames = {category: _generate_synthetic_category(category, size) for category in STANDARD_FIELDS}
    return IndicatorData(frames=frames)


def assemble_records(indicator_data: IndicatorData) -> pd.DataFrame:
    merged = None
    for category, frame in indicator_data.frames.items():
        category_columns = {f"{category}_{col}": values for col, values in frame.items()}
        df = pd.DataFrame(category_columns)
        if merged is None:
            merged = df
        else:
            merged = pd.concat([merged, df], axis=1)
    assert merged is not None
    merged["return"] = np.random.default_rng(123).normal(0.05, 0.2, size=len(merged))
    merged["scene"] = np.random.default_rng(456).choice(20, size=len(merged))
    return merged


def load_payload_records(size: int = 400) -> List[Dict[str, Dict[str, float]]]:
    frames = load_indicator_frames(size).frames
    records: List[Dict[str, Dict[str, float]]] = []
    for i in range(size):
        payload = {category: frames[category].iloc[i].to_dict() for category in frames}
        records.append(standardise(payload))
    return records


def load_dataset(size: int = 400) -> Tuple[pd.DataFrame, List[Dict[str, Dict[str, float]]]]:
    indicator_data = load_indicator_frames(size)
    return assemble_records(indicator_data), load_payload_records(size)
