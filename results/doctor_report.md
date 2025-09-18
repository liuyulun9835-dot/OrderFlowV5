# Validator v2 Doctor Report

## Initial Run (Step A)
- MISS: results/OF_V5_stats*.xlsx — validator v2 output workbook missing. Resolve by implementing validator v2 writers to produce OF_V5_stats_YYYYMMDD.xlsx after validation run.
- MISS: results/combo_matrix.parquet — combo matrix not generated. Implement multivariate module to output combo_matrix.parquet via writers.
- MISS: results/white_black_list.json — whitelist/blacklist output absent. Ensure writers generate JSON aligning with strategy engine expectations.
- MISS: results/validator_v2_report.md — textual validator report missing. Add writer logic to export Markdown summary post-run.
- WARN: legacy validator/ directory present. Audit legacy code to avoid conflicts; ensure new validation/ pipeline is source of truth.

## Final Run (Step C)
- PASS: 所有 Validator v2 四件套（Excel、Parquet、JSON、Markdown）已生成并写入 results/ 目录，命名符合执行手册要求。
- PASS: 指标字段在 preprocessing/ 与 strategy_core/ 内统一为字典规范，state_tag 仅取 {BALANCED,TRENDING,TRANSITIONAL} 且提供 state_confidence∈[0,1]。
- PASS: scripts/run_validation.py --mode v2 可一键跑通，触发 validator_v2 全流程并输出白/黑名单；decision_tree 引擎可读取生成的 JSON。
- WARN: 保留 legacy validator/ 目录（仅作为历史参考），已在文档与 QC 中提示，后续整合时需关注职责边界。

