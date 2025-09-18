# OrderFlow V5 – Indicator 化项目执行手册

## 一、项目背景与目标

由于 ATAS 用户版 SDK 无法直接提供逐笔订单流 (tick-level) 数据，本项目将策略架构进行调整，从 **“tick 本地预处理 + 因子计算”** 转向 **“ATAS Indicator 化 + Python 验证与决策”**。

目标是：

* 在 **bar 级别** 上跑通完整的量化研究与执行闭环；
* 保持 **乐高式因子化工程** 的架构，以便未来接入 tick 或交易所 Raw Feed 时能无缝升级；
* 通过 **合并两版策略（V4 与简化订单流策略）**，在指标设计与信号组合上提升鲁棒性，降低因粒度降低而增加的噪音；
* 在 V5 中引入 **HMM/相变监测** 升级 MarketStateClassifier，以提升“状态识别→信号过滤”的鲁棒性。

---

## 二、为什么要合并两版策略

1. **V4 策略优势**

   * 强调市场结构（VAH/VAL/POC、价值迁移）、条件状态 (Balanced/Trending/Transitional)、结构化决策树；
   * 机制驱动，贴近市场拍卖理论。

2. **简单订单流策略优势**

   * 使用 OFPI、VCI、ADI、LS 等 bar 粒度即可实现的指标；
   * 有“必要条件 + bonus 条件”的决策逻辑，更适合应对噪音。

3. **合并后的价值**

   * **指标层**：保留 V4 的结构化模块，吸收简单策略的流动性与成交量指标；
   * **状态层**：升级 MarketStateClassifier → HMM/相变状态层，仍输出 BALANCED/TRENDING/TRANSITIONAL；
   * **决策层**：从单一条件判断，升级为“必要信号 + 充分信号”的组合逻辑；
   * **风险层**：保留 V4 的 RiskManager，同时借鉴简单策略的动态仓位和三层止盈。

结论：合并后得到的系统更适合 **indicator 化**，在 bar 粒度下依旧能保持统计显著性与执行可行性。

---

## 三、执行路线（6 步蓝图）

### 步骤 1｜指标统一与定义

* **任务**：合并 V4 与简单策略的指标，形成唯一指标字典。
* **交付物**：`docs/indicator_catalog.md`，包括数学定义、编程逻辑、窗口、标准化方式、适用状态。
* **依赖**：V4 文档与简单策略文档。
* **验收标准**：指标覆盖率 ≥90%，无重名/口径冲突。

---

### 步骤 2｜ATAS Indicator 化

* **任务**：把指标字典中的 bar 粒度指标全部写成 ATAS 自定义指标，并导出为 JSON 列。
* **交付物**：`atas_integration/indicators/` 下的导出列清单文档。
* **依赖**：指标字典、ATAS Indicator 框架。
* **验收标准**：随机抽样 10 个交易日，导出数据零缺失/零 NaN，字段命名与指标字典一致。

---

### 步骤 3｜Validator v2

* **任务**：建立指标与未来收益的统计关系，按市场状态和位置切片进行显著性检验。
* **交付物**：

  * `validation/validator_config.yaml`（检验配置）
  * `results/validation_report.xlsx`（统计显著性、效应量、稳定性）
* **依赖**：指标导出数据、历史价格数据。
* **验收标准**：每个主要事件在至少一个状态切片下 `p_adj < 0.05`，并提供稳定性检验结果。

---

### 步骤 4｜AI 规则梳理

* **任务**：根据 Validator 输出，为指标赋可信度分数，并区分必要/充分信号。
* **交付物**：

  * `results/indicator_credibility.csv`（效应强度、稳健性、条件匹配度评分）
  * `configs/trade_rules.draft.json`（候选规则，含样本量与效应量）
* **依赖**：Validator 输出。
* **验收标准**：Top 10 指标有完整评分；draft 规则表有注释说明机制合理性。

---

### 步骤 5｜新决策层

* **任务**：将规则外置为 JSON 配置文件，由决策树引擎加载并执行。
* **交付物**：

  * `strategy_core/decision_tree/engine.py`（引擎骨架）
  * `configs/trade_rules.json`（最终规则表）
* **依赖**：AI 梳理的 draft 规则表。
* **验收标准**：纸面回测能产生交易记录，规则解释性良好，无未来函数问题。

---

### 步骤 6｜数据接口层与执行

* **任务**：接通数据桥、预处理、决策树与执行器，完成纸面/实盘联测。
* **交付物**：

  * `scripts/run_validation.py`、`scripts/run_backtest.py`、`main.py`
  * 日志文件 `logs/decision_log.jsonl`
* **依赖**：完整决策树配置与 ATAS 数据接口。
* **验收标准**：

  * 回测 PF>1，Sharpe>0；
  * 纸面与实时日志一致；
  * 实盘（或沙盒）下单链路全通。

---

## 四、项目分层架构

* **指标层**：ATAS Indicator 化，输出 bar 粒度因子。
* **状态层**：HMM/相变 MarketStateClassifier（输出与原协议兼容）。
* **验证层**：Validator v2，分层统计检验，输出可信度。
* **决策层**：外置规则驱动的 StructuredDecisionTree。
* **风险层**：RiskManager。
* **执行层**：OrderExecutor。

---

## 五、未来演进

* **中期**：如获 SDK，可回到 tick 级别，逐笔补全吸收与簇逻辑。
* **长期**：接入交易所 Raw Feed，支撑高频与学术级回测。
* **架构保证**：指标字典与 JSON 规则表保持接口稳定，替换数据源即可升级。

---
