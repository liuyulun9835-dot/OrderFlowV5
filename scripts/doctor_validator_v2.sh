#!/usr/bin/env bash
set -e

echo "== [1] 目录与关键文件 =="
req_dirs=("preprocessing" "strategy_core" "validation" "results" "scripts" "configs")
for d in "${req_dirs[@]}"; do [ -d "$d" ] || { echo "MISS: $d"; exit 1; }; done
req_md=("OrderFlow_V5_indicator_catalog.md" "OrderFlow_V5_execution_manual.md" "order_flow_v_5_validator_v_2_执行手册.md")
for f in "${req_md[@]}"; do [ -f "$f" ] || { echo "MISS: $f"; exit 1; }; done

echo "== [2] Validator v2 配置 =="
cfg=("validation/configs/validator_v2.yaml" "validation/configs/scenes_whitelist.yaml" \
     "validation/configs/indicators.yaml" "validation/configs/costs.yaml")
for f in "${cfg[@]}"; do [ -f "$f" ] || echo "MISS: $f"; done

echo "== [3] Validator v2 代码骨架 =="
py=("validation/validator_v2.py" "validation/src/loaders.py" "validation/src/scenes.py" \
    "validation/src/triggers.py" "validation/src/labels.py" "validation/src/univariate.py" \
    "validation/src/multivariate.py" "validation/src/stability.py" "validation/src/costs.py" \
    "validation/src/writers.py" "validation/src/qc.py")
for f in "${py[@]}"; do [ -f "$f" ] || echo "MISS: $f"; done

echo "== [4] 执行脚本 =="
[ -f "scripts/run_validation.py" ] || echo "MISS: scripts/run_validation.py (需支持 --mode v2)"

echo "== [5] 指标字段规范（抽样检查） =="
# 期望出现在 features parquet 的字段（可按需增删，与指标字典一致）
fields=(poc vah val near_val near_vah near_poc value_migration value_migration_speed value_migration_consistency \
        bar_delta cvd cvd_ema_fast cvd_ema_slow cvd_macd cvd_rsi cvd_z imbalance \
        nearest_support nearest_resistance nearest_lvn nearest_hvn in_lvn \
        absorption_detected absorption_strength absorption_side \
        volume vol_pctl atr atr_norm_range keltner_pos vwap_session vwap_dev_bps \
        ls_norm session_id state_tag state_confidence)
# 仅在本地已跑完 preprocessing/ 落盘时检查：
test -f "data/processed/features.parquet" && python - <<'PY'
import pandas as pd
df = pd.read_parquet("data/processed/features.parquet")
expect = """poc vah val near_val near_vah near_poc value_migration value_migration_speed value_migration_consistency
bar_delta cvd cvd_ema_fast cvd_ema_slow cvd_macd cvd_rsi cvd_z imbalance
nearest_support nearest_resistance nearest_lvn nearest_hvn in_lvn
absorption_detected absorption_strength absorption_side
volume vol_pctl atr atr_norm_range keltner_pos vwap_session vwap_dev_bps
ls_norm session_id state_tag state_confidence""".split()
miss=[c for c in expect if c not in df.columns]
bad=[c for c in df.columns if c in ("large_z","imbalance_pct")]  # 典型旧名
print("MISSING_FIELDS:", miss)
print("DEPRECATED_FIELDS:", bad)
assert not miss, "缺字段"
assert not bad, "仍有旧名"
PY

echo "== [6] 输出物存在性（跑完一次 validator v2 后检查） =="
for f in results/OF_V5_stats*.xlsx results/combo_matrix.parquet results/white_black_list.json results/validator_v2_report.md; do
  [ -e $f ] || echo "MISS: $f"
done

echo "== [7] 冲突目录 =="
[ -d "validator" ] && echo "WARN: 存在 legacy validator/ 目录，注意与 validation/ 并存的职责边界"
echo "DONE"
