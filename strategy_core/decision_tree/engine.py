"""Decision tree engine that consumes validator v2 white/black lists."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

CONFIG_PATH = Path("configs/trade_rules.json")
VALIDATOR_RESULTS = Path("results/white_black_list.json")


class DecisionTreeEngine:
    """Simple adapter to load trade rules coming from validator v2."""

    def __init__(self, config_path: Path = CONFIG_PATH, validator_path: Path = VALIDATOR_RESULTS) -> None:
        self.config_path = config_path
        self.validator_path = validator_path
        self.whitelist: Iterable[str] = []
        self.blacklist: Iterable[str] = []
        self._load_rules()

    def _load_json(self, path: Path) -> Optional[Dict[str, Iterable[str]]]:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_rules(self) -> None:
        validator_rules = self._load_json(self.validator_path)
        config_rules = self._load_json(self.config_path)
        rules = validator_rules or config_rules or {"whitelist": [], "blacklist": []}
        self.whitelist = self._normalise_entries(rules.get("whitelist", []))
        self.blacklist = self._normalise_entries(rules.get("blacklist", []))
        if validator_rules and (validator_rules != config_rules):
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open("w", encoding="utf-8") as handle:
                json.dump(rules, handle, indent=2, ensure_ascii=False)

    @staticmethod
    def _normalise_entries(entries: Sequence | Iterable) -> Iterable[str]:
        normalised = []
        for item in entries:
            if isinstance(item, dict):
                if "scene" in item:
                    normalised.append(item["scene"])
                elif "name" in item:
                    normalised.append(item["name"])
                elif "expression" in item:
                    normalised.append(item["expression"])
            else:
                normalised.append(str(item))
        return normalised

    def is_scene_allowed(self, scene: str) -> bool:
        if scene in self.blacklist:
            return False
        if not self.whitelist:
            return True
        return scene in self.whitelist


__all__ = ["DecisionTreeEngine"]
