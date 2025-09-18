"""Validator v2 entrypoint."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import yaml

from validation.src import costs, labels, loaders, multivariate, qc, scenes, stability, triggers, univariate, writers


@dataclass
class ValidatorConfig:
    results_dir: Path
    scenes_whitelist: Path
    indicator_config: Path
    costs_config: Path
    minimum_samples: int
    fdr_alpha: float
    stability_threshold: float

    @classmethod
    def from_yaml(cls, path: Path) -> "ValidatorConfig":
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return cls(
            results_dir=Path(payload["results_dir"]),
            scenes_whitelist=Path(payload["scenes_whitelist"]),
            indicator_config=Path(payload["indicator_config"]),
            costs_config=Path(payload["costs_config"]),
            minimum_samples=int(payload.get("minimum_samples", 300)),
            fdr_alpha=float(payload.get("fdr_alpha", 0.10)),
            stability_threshold=float(payload.get("stability_threshold", 0.6)),
        )


class ValidatorV2:
    def __init__(self, config_path: Path | None = None) -> None:
        config_path = config_path or Path("validation/configs/validator_v2.yaml")
        self.config = ValidatorConfig.from_yaml(config_path)
        self.scene_universe = scenes.SceneUniverse.from_yaml(self.config.scenes_whitelist)
        with self.config.costs_config.open("r", encoding="utf-8") as handle:
            self.cost_configs: Dict[str, Dict[str, float]] = yaml.safe_load(handle)
        writers.ensure_results_dir(self.config.results_dir)

    def _prepare_dataset(self) -> pd.DataFrame:
        dataset, _ = loaders.load_dataset()
        label_artifacts = labels.make_labels(dataset)
        dataset = dataset.copy()
        dataset["forward_return"] = label_artifacts.forward_returns
        dataset["label"] = label_artifacts.primary_label
        dataset = dataset.join(label_artifacts.filters)
        dataset = dataset.join(label_artifacts.meta_signals)
        return dataset

    def run(self) -> Dict[str, Path]:
        dataset = self._prepare_dataset()

        numeric_columns = dataset.select_dtypes(include=["number"]).columns
        metrics = [
            column
            for column in numeric_columns
            if column
            not in {
                "label",
                "forward_return",
                "RE",
                "HV",
                "HF",
            }
            and not column.startswith("U")
        ]

        univariate_config = univariate.UnivariateConfig(
            metrics=metrics,
            min_samples=self.config.minimum_samples,
            fdr_alpha=self.config.fdr_alpha,
            stability_threshold=self.config.stability_threshold,
        )
        univariate_result = univariate.compute_univariate(dataset, "label", univariate_config)

        stability_result = stability.compute_stability(dataset, "label")
        qc_report = qc.run_qc(
            dataset,
            "label",
            self.config.minimum_samples,
            stability_result.score,
            self.config.stability_threshold,
        )

        multivariate_result = multivariate.run_regressions(
            dataset,
            label_column="label",
            forward_returns=dataset["forward_return"],
            controls=["session_id", "atr_norm_range", "spread_bps", "state_tag", "ls_norm"],
        )

        cost_result = costs.evaluate_costs(dataset["forward_return"], self.cost_configs)

        trigger_summary = triggers.build_trigger_matrix(dataset, ["U1", "U2", "U3"])  # used for QC context

        whitelist, blacklist = writers.make_scene_lists(univariate_result.summary, self.scene_universe.whitelist)
        qc_summary = {
            "samples": str(len(dataset)),
            "qc_pass": str(qc_report.is_valid()),
            "stability": f"{stability_result.score:.2f}",
            "whitelist": f"{len(whitelist)} scenes",
            "trigger_thresholds": ", ".join(
                f"{name}>= {value:.2f}" for name, value in trigger_summary.thresholds.items()
            ),
        }

        artifacts = writers.write_outputs(
            self.config.results_dir,
            univariate_result.summary,
            multivariate_result.combinations,
            multivariate_result.state_breakdown,
            cost_result,
            whitelist,
            blacklist,
            multivariate_result.combo_matrix,
            qc_summary,
        )

        writers.sync_trade_rules(Path("configs/trade_rules.json"), {"whitelist": whitelist, "blacklist": blacklist})

        return artifacts


def run() -> Dict[str, Path]:
    return ValidatorV2().run()
