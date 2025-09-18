# OrderFlow V5 – Validator v2 执行手册（对齐指标字典 + 白名单完整版）

> 目的：把 V5 的指标检验做成**可复制、可审计、可配置**的流水线。核心是“两段式净化”：
> **闸门**（20 个 AMT 场景白名单，限定“在哪些语境里测”） + **滤网**（RE/HV/HF 三类事件分层，提纯“哪些触发真有用”），最后在“干净样本”上做多变量**提频/提强**协同检验，输出执行层可用的**白/黑名单**与**统计矩阵**。

---

## 1. 适用范围与交付物
- **适用范围**：V5 指标（MSI/MFI/KLI + 成交/动量/流动性/状态）在 1m/5m 粒度下的单/多变量统计检验。
- **交付物**：
  1) `OF_V5_stats_YYYYMMDD.xlsx`（与模板一致）
  2) `combo_matrix.parquet`（组合矩阵）
  3) `white_black_list.json`（执行白/黑名单）
  4) `validator_v2_report.md`（运行配置 + 审计摘要）

---

## 2. 指标字段字典（严格对齐项目《OrderFlow_V5_indicator_catalog.md》）
> **只使用以下字段命名**，便于指标、验证、执行三层对齐。

### 2.1 市场结构指标（MSI）
- `poc, vah, val`：结构位
- `near_val / near_vah / near_poc`：是否在缓冲区内
- `value_migration`：POC/VA 迁移方向：`"UP"|"DOWN"|"FLAT"`
- `value_migration_speed`：迁移速度（连续变化率）
- `value_migration_consistency`：迁移方向一致性（0–1）
- **参数**：`val_buffer, vah_buffer, poc_buffer, migration_lookback`

### 2.2 资金流指标（MFI）
- `bar_delta`：bar 内买卖差
- `cvd`：累计成交量差
- `cvd_ema_fast / cvd_ema_slow / cvd_macd`：CVD 平滑动量
- `cvd_rsi / cvd_z`：CVD 归一化
- `imbalance`：主动买卖比（按分位阈值）
- **参数**：`z_window, imbalance_pctl`

### 2.3 关键位指标（KLI）
- `nearest_support / nearest_resistance`
- `nearest_lvn / nearest_hvn`
- `in_lvn`：是否处于 LVN 半径内
- `absorption_detected`，`absorption_strength`（0–1），`absorption_side`：`"bid"|"ask"`
- **参数**：`absorption_min, lvn_radius_bps`

### 2.4 成交与动量/位置
- `volume, vol_pctl`；`atr, atr_norm_range`；`keltner_pos`（-1~+1）
- `vwap_session, vwap_dev_bps`（会话 VWAP 与偏离）

### 2.5 流动性与时段
- `ls_norm`（0–1），`session_id`（asia/eu/us）

### 2.6 市场状态
- `state_tag`：`"BALANCED"|"TRENDING"|"TRANSITIONAL"`
- `state_confidence`：状态置信度（0–1）

> 以上命名在配置表达式、统计输出、白名单规则内必须一致。

---

## 3. 输入/输出与目录
### 3.1 输入
- Bar 数据与特征：`time, open, high, low, close, ret_*m,` 上述所有指标字段
- **禁止未来信息**：特征在 t 时刻只能用 t 及以前的数据生成

### 3.2 输出（Excel 各 Sheet）
- `univariate`：单因子-场景-窗口统计（含 RE/HV/HF 比例）
- `combinations`：组合矩阵（“增强/降低/—”+ 交互项 q + 净效应 + 稳定性 + 状态依赖）
- `state_breakdown`：状态分解
- `cost_sensitivity`：成本敏感性
- `rules_white_list`：20 场景的表达式与过滤（便于执行）

### 3.3 目录建议
```
validator_v2/
  configs/
    validator_v2.yaml
    scenes_whitelist.yaml
    indicators.yaml
    costs.yaml
  data/
    bars_1m.parquet
    features.parquet
  src/
    run.py loaders.py scenes.py triggers.py labels.py
    univariate.py multivariate.py stability.py costs.py writers.py qc.py
  out/
    OF_V5_stats_YYYYMMDD.xlsx combo_matrix.parquet white_black_list.json report.md
```

---

## 4. 配置（最小可运行）
```yaml
run:
  start: "2024-01-01"
  end:   "2025-08-31"
  horizons: ["5m","15m","30m","60m"]
  write_excel: true
filters_global:
  - "ls_norm > 0.5"
  - "atr_norm_range >= 0.3 and atr_norm_range <= 2.0"
  - "state_confidence > 0.6"
scenes: "configs/scenes_whitelist.yaml"
indicators: "configs/indicators.yaml"
costs: "configs/costs.yaml"
cv:
  scheme: purged_kfold
  k: 5
  embargo_bars: 5
statistics:
  fdr_alpha: 0.10
  n_min: 300
  rolling_window_days: 90
labels:
  RE: "signed_r_15m > median(signed_r_15m) + 1.5*MAD"
  HV: "vol_15m > median(vol_15m) + 1.5*MAD"
  HF:
    window:  "60m"
    method:  "auto"   # poisson->negbin if overdispersed
    alpha:   0.05
meta_signals:
  U1: "RE & HF & !HV"   # 稳健
  U2: "RE & HF"         # 进攻
  U3: "RE & !HV"        # 保守
multivariate:
  controls: ["session_id","atr_norm_range","spread_bps","state_tag","ls_norm"]
  decision:
    must: ["(q_rate<=0.10) or (q_sev<=0.10)", "net_uplift>0", "stability>=0.6", "N>=300"]
```

---

## 5. 白名单（20 条 AMT 场景，**完整版**）
> 语法：全部使用第 2 节字段名；`pXX` 表示分位阈值（如 `imbalance >= pctl60`）。可在 `indicators.yaml` 定义占位参数：`absorption_min, lvn_radius_bps, imbalance_pctl, val_buffer, vah_buffer, poc_buffer` 等。

### A. 平衡/响应式（6 条）
**A1｜VAL 回归多**（Responsive Long to POC）
- **trigger**：`near_val & absorption_detected & absorption_side=="bid" & absorption_strength>=absorption_min & (cvd_z>0.5 or imbalance>=pctl60) & state_tag=="BALANCED"`
- **filters**：`vol_pctl>=0.3 & ls_norm>0.5`
- **exits**：`TP=POC`；`SL=VAL*(1-0.5*val_buffer)`；可选 `timeout=60m`
- **notes**：回归中值，禁追趋势

**A2｜VAH 回归空**（Responsive Short to POC）
- **trigger**：`near_vah & absorption_detected & absorption_side=="ask" & absorption_strength>=absorption_min & (cvd_z<-0.5 or imbalance<=pctl40) & state_tag=="BALANCED"`
- **filters**：同 A1
- **exits**：`TP=POC`；`SL=VAH*(1+0.5*vah_buffer)`

**A3｜POC 反转跟随**（POC Flip）
- **trigger**：`near_poc & cvd_macd crosses 0 & ! (absorption_detected & absorption_side in ["ask","bid"])`
- **filters**：`value_migration_consistency not strongly opposite`
- **exits**：`TP=VAL/VAH`（触边出场）

**A4｜区间内 LVN 反弹（多）**
- **trigger**：`in_lvn & cvd_z>0.5 & state_tag in ["BALANCED","TRANSITIONAL"]`
- **filters**：`! (absorption_detected & absorption_side=="ask")`
- **exits**：`TP=nearest_hvn`

**A5｜区间内 LVN 回落（空）**
- **trigger**：`in_lvn & cvd_z<-0.5 & state_tag in ["BALANCED","TRANSITIONAL"]`
- **filters**：`! (absorption_detected & absorption_side=="bid")`
- **exits**：`TP=nearest_hvn`

**A6｜中性日（两边 RE）边缘→中值（双向）**
- **trigger**：`(near_val or near_vah) & value_migration=="FLAT" & absorption_detected`
- **filters**：`vol_pctl>=0.3`
- **exits**：`TP=POC`；`SL=边缘缓冲`

### B. 趋势/主动性（8 条）
**B7｜RE 向上→趋势延续（多）**
- **trigger**：`close>vah & value_migration=="UP" & cvd_z>0.7 & cvd_macd>0 & vol_pctl>0.7 & state_tag=="TRENDING"`
- **filters**：`! (absorption_detected & absorption_side=="ask")`
- **exits**：`TP=nearest_hvn or trailing(keltner_pos)`

**B8｜RE 向下→趋势延续（空）**
- **trigger**：`close<val & value_migration=="DOWN" & cvd_z<-0.7 & cvd_macd<0 & vol_pctl>0.7 & state_tag=="TRENDING"`
- **filters**：`! (absorption_detected & absorption_side=="bid")`
- **exits**：同 B7 对称

**B9｜突破后回抽未回补（多）**
- **trigger**：`(close>vah & pullback_to_vah & not filled_gap) & imbalance>=pctl70 & state_tag in ["TRENDING","TRANSITIONAL"]`
- **filters**：`value_migration_speed>=0`
- **exits**：`TP=next structural (prior_high or nearest_hvn)`

**B10｜突破失败反手（空）**
- **trigger**：`(break_vah_fail & back_to_VA) & absorption_detected & absorption_side=="ask" & cvd_macd<0`
- **filters**：`vol_pctl>=0.3`
- **exits**：`TP=POC or VAL`

**B11｜向上趋势中的 LVN 穿越（多）**
- **trigger**：`state_tag=="TRENDING" & value_migration=="UP" & in_lvn & cvd_z>0.5 & ! (absorption_detected & absorption_side=="ask")`
- **filters**：`ls_norm>0.5`
- **exits**：`TP=nearest_hvn`

**B12｜向下趋势中的 LVN 穿越（空）**
- **trigger**：`state_tag=="TRENDING" & value_migration=="DOWN" & in_lvn & cvd_z<-0.5 & ! (absorption_detected & absorption_side=="bid")`
- **filters**：`ls_norm>0.5`
- **exits**：`TP=nearest_hvn`

**B13｜开盘驱动（Open Drive）顺势（双向）**
- **trigger**：`session_id changes to open & vol_pctl>0.8 & extreme(imbalance) & value_migration in direction of drive`
- **filters**：`state_confidence>0.6`
- **exits**：`TP=结构位 或 trailing`

**B14｜RE 之后继续单边（单边日，双向）**
- **trigger**：`value_migration_consistency>0.6 & expanding(cvd_macd)`
- **filters**：`abs(keltner_pos) <= 1.0`
- **exits**：`trailing`

### C. 形态（4 条）
**C15｜P 形（空头回补）延续（多）**
- **trigger**：`P_shape_detected & cvd_z>0.6 & value_migration=="UP"`
- **filters**：`! (absorption_detected & absorption_side=="ask")`
- **exits**：`TP=nearest_hvn`

**C16｜b 形（多头抛售）延续（空）**
- **trigger**：`b_shape_detected & cvd_z<-0.6 & value_migration=="DOWN"`
- **filters**：`! (absorption_detected & absorption_side=="bid")`
- **exits**：`TP=nearest_hvn`

**C17｜双分布日（中场切换，双向）**
- **trigger**：`double_distribution & hvn_switch & migration_accel>0 & prefer(in_lvn)`
- **filters**：`ls_norm>0.5`
- **exits**：`TP=opposite_hvn`

**C18｜外包日（Outside Day）顺延（双向）**
- **trigger**：`keltner_expand & vol_pctl>0.8 & extreme(cvd_z or imbalance)`
- **filters**：`state_tag in ["TRANSITIONAL","TRENDING"]`
- **exits**：`TP=structure or trailing`

### D. VWAP / 转场（2 条）
**D19｜VWAP 夺回（下→上，多）**
- **trigger**：`vwap_dev_bps crosses from negative to positive & cvd_macd>0 & imbalance>=pctl60`
- **filters**：`distance_to(vah) > val_buffer`（上方空间不足则减半）
- **exits**：`TP=nearest_hvn or VAH`

**D20｜VWAP 失守（上→下，空）**
- **trigger**：`vwap_dev_bps crosses from positive to negative & cvd_macd<0 & imbalance<=pctl40`
- **filters**：`distance_to(val) > vah_buffer`
- **exits**：`TP=nearest_hvn or VAL`

> 以上每条在 `rules_white_list` 与 `scenes_whitelist.yaml` 中各保留一份：前者用于**执行层规则**，后者用于**验证切片**（只在场景=真时做统计）。

---

## 6. 单变量检验（闸门→滤网→评分）
**Step 1｜闸门**：仅保留“任一场景=真”的样本。

**Step 2｜阈值触发**：每个指标的触发布尔列 `I_indicator`（可多阈值并行）。

**Step 3｜标签分层**（在“场景=真 & 触发=真”的子样本上）：
- 计算 `signed_r_h`（按做多/做空意图对齐）与 `vol_h`；
- 打标签：`RE/HV/HF`（RE/HV 用分位或 MAD；HF 用泊松/负二项窗口计数）。

**Step 4｜重合度**：R、V、F 的覆盖率、Lift、Jaccard；滚动窗口复验稳定性。

**Step 5｜元信号**：`U1=RE∩HF∩¬HV`、`U2=RE∩HF`、`U3=RE∩¬HV`。

**Step 6｜评分与门槛**：
`Score ≈ 事件率(λ̂) × 事件强度(净均值) × 稳定性`；
保留条件：`N≥300`、`Score>0`、`Stability≥0.6`、q≤0.10（FDR）。

**Step 7｜写表**：把各指标×场景×窗口的统计写入 `univariate`。

---

## 7. 多变量检验（仅用“元信号砖”做协同）
**候选生成**：层级门控（父组合合格才扩展），Apriori 支持度 `N≥300`。

**提频（Rate uplift）**：
- 因变量：单位时间“事件=1”的次数（可选 RE 或 U1）。
- 模型：泊松→若过度离散改负二项；
`log(λ)=β0 + β_A U_A + β_B U_B + β_AB U_A·U_B + controls`；
关注交互项 `β_AB`（q 值）。

**提强（Severity uplift）**：
- 条件在“事件=1”的子样本；`severity=signed_r_h`（或尾部收益）。
- 线性/分位回归：`severity=α+δ_A U_A+δ_B U_B+δ_AB U_A·U_B+controls+ε`；
关注交互项 `δ_AB`（q 值）。

**净效应 + 稳定性 + 状态分解**：
- 扣费净均值/命中率/回撤；滚动窗口稳定性≥0.6；
- 在 `TRENDING/BALANCED/...` 下各跑一遍，写明“何时有效”。

**决策**：
- 满足 `decision.must` → **增强(↑)** 入白名单；交互为负或不稳 → **降低(↓)**；其余 **—**。
- 写入 `combinations/state_breakdown/cost_sensitivity` 与 `white_black_list.json`。

---

## 8. 成本、稳定性与交叉验证
- **成本**：统一以净效应为准（手续费/滑点/点差）；敏感性场景：`base / +50% / ×2`。
- **时间序列 CV**：Purged K-Fold + Embargo；
- **滚动稳定性**：每 90 天为窗，统计“为正”的比例为 `stability_score`。

---

## 9. 审计检查（QC）
- [ ] 无未来信息；
- [ ] 全局过滤生效（ls/atr/state_confidence 等）；
- [ ] N、覆盖期满足门槛；
- [ ] 过度离散检查（Poisson→NegBin）；
- [ ] FDR（q 值）统一 α；
- [ ] 成本敏感性；
- [ ] 状态分解；
- [ ] 配置/版本/随机种子写入报告，可复现。

---

## 10. 常见问题（FAQ）
- **泊松能否拟合收益？** 不能。泊松只用于**次数**；收益/强度用线性/分位/极值模型。
- **样本不足？** 合并邻近阈值、延长时间或暂缓结论；`N<300` 仅做观察。
- **先验会不会错？** 场景是闸门，数据（RE/HV/HF + FDR）是证伪器；两者循环迭代。

---

## 附录 A｜`scenes_whitelist.yaml` 片段（与第 5 节完全一致）
```yaml
SCN_VAL_REVERT_L: "near_val & absorption_detected & absorption_side=='bid' & absorption_strength>=absorption_min & (cvd_z>0.5 or imbalance>=pctl60) & state_tag=='BALANCED'"
SCN_VAH_REVERT_S: "near_vah & absorption_detected & absorption_side=='ask' & absorption_strength>=absorption_min & (cvd_z<-0.5 or imbalance<=pctl40) & state_tag=='BALANCED'"
SCN_POC_FLIP:     "near_poc & cross(cvd_macd,0) & !(absorption_detected)"
SCN_LVN_BOUNCE_L: "in_lvn & cvd_z>0.5 & state_tag in ['BALANCED','TRANSITIONAL'] & !(absorption_detected & absorption_side=='ask')"
SCN_LVN_DROP_S:   "in_lvn & cvd_z<-0.5 & state_tag in ['BALANCED','TRANSITIONAL'] & !(absorption_detected & absorption_side=='bid')"
SCN_EDGE_TO_POC:  "(near_val or near_vah) & value_migration=='FLAT' & absorption_detected & vol_pctl>=0.3"
SCN_TREND_UP:     "close>vah & value_migration=='UP' & cvd_z>0.7 & cvd_macd>0 & vol_pctl>0.7 & state_tag=='TRENDING' & !(absorption_detected & absorption_side=='ask')"
SCN_TREND_DOWN:   "close<val & value_migration=='DOWN' & cvd_z<-0.7 & cvd_macd<0 & vol_pctl>0.7 & state_tag=='TRENDING' & !(absorption_detected & absorption_side=='bid')"
SCN_PB_NO_FILL_L: "close>vah & pullback_to_vah & !filled_gap & imbalance>=pctl70 & state_tag in ['TRENDING','TRANSITIONAL']"
SCN_FAIL_AUCTION: "break_vah_fail & back_to_VA & absorption_detected & absorption_side=='ask' & cvd_macd<0 & vol_pctl>=0.3"
SCN_TR_LVN_UP:    "state_tag=='TRENDING' & value_migration=='UP' & in_lvn & cvd_z>0.5 & !(absorption_detected & absorption_side=='ask')"
SCN_TR_LVN_DN:    "state_tag=='TRENDING' & value_migration=='DOWN' & in_lvn & cvd_z<-0.5 & !(absorption_detected & absorption_side=='bid')"
SCN_OPEN_DRIVE:   "session_open & vol_pctl>0.8 & extreme(imbalance) & value_migration in drive_dir & state_confidence>0.6"
SCN_ONEWAY_DAY:   "value_migration_consistency>0.6 & expanding(cvd_macd) & abs(keltner_pos)<=1.0"
SCN_P_SHAPE:      "P_shape_detected & cvd_z>0.6 & value_migration=='UP'"
SCN_b_SHAPE:      "b_shape_detected & cvd_z<-0.6 & value_migration=='DOWN'"
SCN_DOUBLE_DIST:  "double_distribution & hvn_switch & migration_accel>0 & in_lvn"
SCN_OUTSIDE:      "keltner_expand & vol_pctl>0.8 & extreme(cvd_z or imbalance) & state_tag in ['TRANSITIONAL','TRENDING']"
SCN_VWAP_RECAP_L: "cross_up(vwap_dev_bps,0) & cvd_macd>0 & imbalance>=pctl60 & distance_to(vah)>val_buffer"
SCN_VWAP_LOSS_S:  "cross_dn(vwap_dev_bps,0) & cvd_macd<0 & imbalance<=pctl40 & distance_to(val)>vah_buffer"
```

---

## 附录 B｜伪代码（核心）
```python
# 单变量
for scene in scenes:
  S = data.query(scene_expr(scene)).pipe(apply_global_filters)
  for ind in indicators:
    trig = S.eval(trigger_expr(ind))
    E = S[trig]
    for h in horizons:
      r = signed_return(E, h)
      v = realized_vol(E, h)
      RE = r > median(r) + 1.5*MAD(r)
      HV = v > median(v) + 1.5*MAD(v)
      HF = poisson_or_negbin_cluster(E["time"], window="60m", alpha=0.05)
      U1, U2, U3 = RE & HF & ~HV, RE & HF, RE & ~HV
      write_univariate(ind, scene, h, stats_from(E, RE, HV, HF, U1, U2, U3))

# 多变量
for combo in candidate_combos_from(meta_signals, min_support=300):
  fit_rate = GLM_count(events_per_unit_time(combo), regressors=[U_A, U_B, U_A*U_B, controls])
  fit_sev  = Regress(severity_given_event(combo), regressors=[U_A, U_B, U_A*U_B, controls])
  write_combo(combo, fit_rate, fit_sev, net_effects, stability, state_split)
```

— 完 —

