"""Scene configuration helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import yaml


@dataclass
class SceneUniverse:
    whitelist: List[str]

    @classmethod
    def from_yaml(cls, path: Path) -> "SceneUniverse":
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        scenes: Iterable[str] = payload.get("scenes", [])
        return cls(whitelist=list(scenes))

    def ensure_scene(self, scene: str) -> bool:
        return scene in self.whitelist
