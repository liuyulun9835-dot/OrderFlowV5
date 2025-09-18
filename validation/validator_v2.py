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

    def run(self) -> Dict[str, Path]:
        dataset, _ = loaders.load_dataset()
        forward_returns, labels_series = labels.make_labels(dataset)
        dataset["label"] = labels_series

        trigger_columns = {col: 0.9 for col in dataset.columns if col.startswith("MFI_")}
        trigger_matrix = triggers.build_trigger_matrix(dataset[list(trigger_columns.keys())], trigger_columns) if trigger_columns else None

        numeric_dataset = dataset.select_dtypes(include=["number"])
        univariate_result = univariate.compute_univariate(numeric_dataset.drop(columns=["scene"]), "label", self.config.fdr_alpha)
        multi_inputs = numeric_dataset
        regression_results = multivariate.run_regressions(multi_inputs, "label")
        stability_result = stability.compute_stability(dataset, "label")
        cost_result = costs.evaluate_costs(forward_returns, self.cost_configs)
        qc_report = qc.run_qc(dataset, "label", self.config.minimum_samples, stability_result.score, self.config.stability_threshold)

        combo_matrix = dataset[["scene", "label"]].copy()
        combo_matrix["scene_name"] = combo_matrix["scene"].apply(lambda idx: self.scene_universe.whitelist[idx % len(self.scene_universe.whitelist)])
        if trigger_matrix is not None:
            combo_matrix = combo_matrix.join(trigger_matrix)

        whitelist = [row.metric for _, row in univariate_result.summary.iterrows() if row.reject]
        blacklist = [scene for scene in self.scene_universe.whitelist if scene not in whitelist[: len(self.scene_universe.whitelist) // 2]]
        rules = {"whitelist": whitelist, "blacklist": blacklist}

        results_dir = self.config.results_dir
        excel_path = results_dir / "OF_V5_stats.xlsx"
        parquet_path = results_dir / "combo_matrix.parquet"
        json_path = results_dir / "white_black_list.json"
        report_path = results_dir / "validator_v2_report.md"

        sheets = {
            "univariate": univariate_result.summary,
            "stability": stability_result.metrics,
            "costs": cost_result,
        }
        for name, result in regression_results.items():
            sheets[f"regression_{name}"] = result.params

        writers.write_excel(excel_path, sheets)
        writers.write_parquet(parquet_path, combo_matrix)
        writers.write_json(json_path, rules)

        markdown_sections = {
            "Validator v2 Report": (
                f"Samples: {len(dataset)}\\n"
                f"FDR α: {self.config.fdr_alpha}\\n"
                f"QC Pass: {qc_report.is_valid()}\\n"
                f"Stability Score: {stability_result.score:.2f}\\n"
            )
        }
        writers.write_markdown(report_path, markdown_sections)
        writers.sync_trade_rules(Path("configs/trade_rules.json"), rules)

        return {
            "excel": excel_path,
            "parquet": parquet_path,
            "json": json_path,
            "markdown": report_path,
        }


def run() -> Dict[str, Path]:
    return ValidatorV2().run()
