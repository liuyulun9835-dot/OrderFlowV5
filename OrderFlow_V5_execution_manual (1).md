# OrderFlow V5 – Execution Manual（统一版）

## 一、项目背景与目标
由于 ATAS 用户版 SDK 无法直接提供逐笔订单流 (tick-level) 数据，本项目转向 **ATAS Indicator 化 + Python 验证与决策** 的架构。  

核心目标：  
- 在 **bar 粒度** 下保持因子化研究的可复现性；  
- 通过 **Validator v2** 形成 **可审计的统计显著性闭环**；  
- **规则外置化**，用 JSON/配置驱动 StructuredDecisionTree；  
- **风险控制层** 与 **执行层** 保持稳定接口，未来能无缝升级 tick/raw feed。  

---

## 二、指标字典（统一规范）
严格对齐《OrderFlow_V5_indicator_catalog.md》与 Validator v2：  

### 市场结构 (MSI)
- `poc, vah, val, near_val, near_vah, near_poc`  
- `value_migration, value_migration_speed, value_migration_consistency`  

### 资金流 (MFI)
- `bar_delta, cvd, cvd_ema_fast, cvd_ema_slow, cvd_macd, cvd_rsi, cvd_z, imbalance`  

### 关键位 (KLI)
- `nearest_support, nearest_resistance, nearest_lvn, nearest_hvn, in_lvn`  
- `absorption_detected, absorption_strength, absorption_side`  

### 成交/动量/位置
- `volume, vol_pctl, atr, atr_norm_range, keltner_pos, vwap_session, vwap_dev_bps`  

### 流动性/时段
- `ls_norm, session_id`  

### 状态
- `state_tag ("BALANCED"|"TRENDING"|"TRANSITIONAL")`  
- `state_confidence (0–1)`  

> 命名必须在 **ATAS 导出 → Validator → 执行层规则** 中保持一致。

---

## 三、执行路线（6 步蓝图）

### 步骤 1｜指标实现
- 将指标字典写为 ATAS Indicator，导出为 JSON。  
- 随机抽样验证：零缺失、零 NaN。  

### 步骤 2｜数据预处理
- Python DataPreprocessor 合并 ATAS 与 Binance 数据。  
- 校验 `required_fields`，生成 Parquet。  

### 步骤 3｜Validator v2
- 运行 `validation/validator_v2.py`：  
  - **单变量检验**：闸门（场景白名单）+ 滤网（RE/HV/HF）→ U1/U2/U3 元信号。  
  - **多变量检验**：Poisson/NegBin + 回归 → 协同提频/提强。  
- 输出：  
  - `OF_V5_stats.xlsx`  
  - `combo_matrix.parquet`  
  - `white_black_list.json`  

### 步骤 4｜规则梳理
- 将白名单事件转为规则表达式。  
- 生成 `configs/trade_rules.draft.json`，含样本量与效应量注释。  

### 步骤 5｜决策层
- `strategy_core/decision_tree/engine.py` 加载规则 JSON。  
- 规则形式：必要信号 + 充分信号，避免未来函数。  

### 步骤 6｜执行与风控
- RiskManager：仓位、日损、冷却、最小 RR。  
- OrderExecutor：纸面/实盘模式，CCXT 下单，带滑点保护与止损调整。  
- 日志：写入 `logs/decision_log.jsonl`。  

---

## 四、白名单场景（20 条完整版）
与 Validator v2 一致，分为：  
- **A 平衡/响应式**：VAL 回归多、VAH 回归空、POC Flip、LVN 反弹/回落、中性日边缘→中值；  
- **B 趋势/主动性**：趋势延续、突破回抽、失败反手、趋势 LVN、Open Drive、单边日；  
- **C 形态**：P 形、b 形、双分布日、Outside Day；  
- **D VWAP/转场**：VWAP 夺回、VWAP 失守。  

> 每条场景同时存在于：  
> - `configs/scenes_whitelist.yaml`（验证层）  
> - `configs/trade_rules.json`（执行层）  

---

## 五、目录树（统一版）
```
orderflow_v5/
├── atas_integration/
│   ├── indicators/           # ATAS 指标导出
│   └── data_bridge/          # 数据桥
├── preprocessing/
│   └── data_preprocessor.py  # 特征生成与落盘
├── strategy_core/
│   └── decision_tree/
│       └── engine.py         # 加载 JSON 规则
├── validation/
│   ├── validator_v2.py       # 主入口
│   ├── configs/
│   │   ├── validator_v2.yaml
│   │   ├── scenes_whitelist.yaml
│   │   ├── indicators.yaml
│   │   └── costs.yaml
├── execution/
│   ├── risk_manager.py
│   ├── order_executor.py
│   ├── position_utils.py
│   └── okx_formatter.py
├── scripts/
│   ├── run_backtest.py
│   ├── run_validation.py
│   └── quickstart_paper.sh / .ps1
├── data/
│   ├── atas/
│   ├── processed/
│   └── sample/
├── results/
│   ├── OF_V5_stats.xlsx
│   ├── combo_matrix.parquet
│   ├── white_black_list.json
│   └── logs/
└── main.py / README.md / pyproject.toml / Dockerfile / .gitignore
```

---

## 六、运行流程（快速开始）
```bash
# 1. 安装依赖
poetry install --no-root

# 2. 数据预处理
poetry run python preprocessing/data_preprocessor.py

# 3. 运行 Validator v2
poetry run python scripts/run_validation.py --out results/OF_V5_stats.xlsx

# 4. 运行回测
poetry run python scripts/run_backtest.py --data data/processed/preprocessed.parquet --out results/backtest

# 5. 启动 Paper 模式
poetry run python main.py --paper
```

---

## 七、审计与复现要求
- 所有指标字段与场景表达式必须与字典/白名单一致；  
- 禁止未来函数；  
- 保证 `N≥300`、FDR α=0.10、滚动窗口稳定性≥0.6；  
- 成本敏感性需提供 base/+50%/×2 三版本。  
