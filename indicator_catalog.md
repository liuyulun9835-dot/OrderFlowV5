# 指标字典 (Indicator Catalog – HMM/相变扩展版)

本表整合 V4 策略、简单订单流策略与 V5 HMM/相变升级方案的指标，统一为 ATAS Indicator 化实现的 bar 粒度版本。

---

## 市场结构指标 (MSI)
- **poc, vah, val**: 成交量加权的结构位。
- **near_val/vah/poc**: 价格是否在缓冲区内。
- **value_migration**: 基于窗口的 POC/VA 中值迁移方向 ("UP"/"DOWN"/"FLAT")。
- **value_migration_speed**: POC/VA 迁移速度（连续变化率）。
- **value_migration_consistency**: POC/VA 迁移方向一致性。  
- **参数**: val_buffer, vah_buffer, poc_buffer, migration_lookback。

## 资金流指标 (MFI)
- **bar_delta**: Bar 内买卖成交量差 (askVol - bidVol)。  
- **cvd**: 累计成交量差 (Cumulative Volume Delta)。  
- **cvd_ema_fast / cvd_ema_slow / cvd_macd**: CVD 平滑动量。  
- **cvd_rsi / cvd_z**: CVD 的 RSI 与 z-score 标准化。  
- **imbalance**: 主动买/卖单比。  
- **参数**: z_window, imbalance_pctl。

## 关键位指标 (KLI)
- **nearest_support/resistance**: 最近的结构支撑/阻力位。  
- **nearest_lvn / nearest_hvn**: 成交低谷/高峰。  
- **in_lvn**: 当前价格是否落在 LVN 半径内。  
- **absorption_detected**: 是否发生吸收 (bar 内成交集中在一侧)。  
- **absorption_strength**: 吸收强度 (0~1)。  
- **参数**: absorption_min, lvn_radius_bps。

## 成交与动量指标
- **volume**: Bar 内成交量。  
- **vol_pctl**: 成交量分位数。  
- **atr / atr_norm_range**: 平均真实波幅及归一化区间。  
- **keltner_pos**: 价格在 Keltner 通道中的相对位置 (-1~+1)。  
- **vwap_session / vwap_dev_bps**: 会话 VWAP 与偏离基点。

## 流动性与时段指标
- **ls_norm**: 流动性评分 (proxy，基于挂单与成交分布)。  
- **session_id**: 交易时段 (亚洲/欧洲/美洲)。  

## HMM 观测特征 (Regime Observations)
> 用于 HMM 状态层训练与解码的观测向量 X_t
- **price_rel_val/vah/poc**: 价格相对 VAL/VAH/POC 的标准化距离。  
- **cvd_features**: {cvd, cvd_z, cvd_macd}。  
- **flow_imbalance**: 买卖不平衡。  
- **absorption_features**: {absorption_detected, absorption_strength}。  
- **volume_features**: {volume, vol_pctl}。  
- **value_migration_features**: {value_migration, value_migration_speed, value_migration_consistency}。

## 相变前兆指标 (Early Warning Signals)
- **ret_var**: 收益滚动方差（临界减速）。  
- **ret_acf1**: 收益一阶自相关（临界减速）。  
- **cvd_skew**: CVD 分布偏度。  
- **cvd_kurt**: CVD 分布峰度。  
- **migration_accel**: POC/VA 迁移加速度。  

这些指标不直接触发开仓，而是作为 HMM 转移概率的修正或阈值调整。

## 市场状态分类
- **BALANCED**: HMM 状态/规则判定 = 平衡。  
- **TRENDING**: HMM 状态/规则判定 = 趋势。  
- **TRANSITIONAL**: HMM 状态/规则判定 = 过渡。  
- **post_prob**: HMM 输出的后验概率向量。  
- **state_confidence**: max(post_prob)，状态置信度。  

## 综合评分 (ScoringEnhancement)
- **money_flow_score**: 基于 cvd_z 与 imbalance。  
- **key_levels_score**: 基于 absorption_strength 与 lvn_confidence。  
- **momentum_score**: vol_pctl 与 cvd_macd 结合。  
- **market_structure_score**: 基于价位与 VAH/VAL 关系。  
- **state_confidence_score**: 来自 HMM 的状态置信度。  
- **综合权重**: MS=0.25, MF=0.25, KLI=0.2, MOM=0.1, STATE=0.2。

---
