# 因子研究注意事项

## 文档目的
记录 Crypto 因子检测中容易被忽视、但会导致回测和实盘差异的细节，作为后续研究与代码实现的检查清单。

## 第一版必须落地的检查
| 检查项 | 必须原因 | 第一版处理 |
|---|---|---|
| Point-in-time universe | 避免用今天币池回测历史 | 每个时间点用当时已上市、未下架、可交易资产生成 universe |
| Listing/Delisting 状态 | 避免删除失败币和下架币历史 | 元数据记录 `listed_time`、`delisted_time`、`tradable_status` |
| 数据可得时间 | 避免使用当时还不可见的数据 | 区分 `event_time`、`available_time`、`ingested_time` |
| 因子与收益错位 | 避免未来 K 线参与因子 | 因子时间必须早于收益标签起点 |
| Universe 筛选滞后 | 避免用未来成交额/市值筛选当期样本 | 当期入池使用上一期或已确认可得数据 |
| 成本后结果 | 避免 IC 好看但不可交易 | 输出手续费、滑点估计、资金费率、换手 |
| 配置版本 | 避免后验调参无法追踪 | 记录 `factor_version`、`test_config_version`、`acceptance_rule_version` |
| 标签生效时间 | 避免用今天分类解释过去 | `primary_category` 记录 `category_effective_time` |

## Universe 与资产池
| 风险 | 典型错误 | 正确做法 |
|---|---|---|
| 幸存者偏差 | 只用今天仍存在的币做历史回测 | 保留历史下架币，下架后不再入池 |
| 当前成分回看 | 用当前 Top100/Top200 回测过去 | 用每个历史时点的滚动排名 |
| 完整历史筛选 | 只保留历史完整的币 | 不要求完整历史，只要求当期可用 |
| 交易暂停忽略 | 回测可交易，实盘无法成交 | `tradable_status != active` 时不入池 |
| 新币处理错误 | 新币上市前已有因子值 | `listed_time <= decision_time` 才可入池 |

## 时间戳与数据可得性
| 字段 | 中文含义 | 用途 |
|---|---|---|
| `event_time` | 市场事件发生时间 | K 线、资金费率、成交等对应的真实市场时间 |
| `available_time` | 策略可使用时间 | 因子计算只能使用该时间之前可见的数据 |
| `ingested_time` | 本地入库时间 | 追踪数据源延迟、回填和重算 |
| `decision_time` | 决策时间 | 生成信号和决定调仓的时间 |
| `label_start_time` | 收益标签起点 | forward return 的开始时间 |
| `label_end_time` | 收益标签终点 | forward return 的结束时间 |

硬规则：

```text
available_time <= decision_time <= label_start_time < label_end_time
```

## 价格、收益与成本
| 风险 | 典型错误 | 正确做法 |
|---|---|---|
| 不可交易价格 | 用 index/mark price 当成交价 | 明确 `price_type`，收益评价和成交假设分开 |
| Close-to-close 幻觉 | 假设能按刚收盘 close 成交 | 第一版使用 next-bar return 或 next-bar executable return |
| 滑点忽略 | 小币收益被高估 | 至少用成交额和简单参与率估算滑点 |
| Funding 忽略 | 永续多空收益失真 | 永续策略输出 `funding_cost` |
| 极端坏点 | 插针或错误 K 线制造虚假收益 | 异常值先标记，再决定是否排除 |

## Crypto 特有问题
| 问题 | 影响 | 第一版处理 |
|---|---|---|
| 代币迁移/换合约 | 价格序列断裂或错误拼接 | 记录迁移映射和断点，不自动拼接 |
| 交易对变更 | 流动性和可交易性口径变化 | 第一版限定 quote 与交易所范围 |
| CEX/DEX 混合 | 成交质量差异很大 | 第一版优先 CEX 或指定交易所集合 |
| 合约上线晚于现货 | 永续历史可交易性被高估 | 单独记录 `contract_listed_time` |
| Funding 结算规则变化 | 资金费率因子时间错位 | 记录 `funding_interval` 和结算时间 |
| 标签回看 | 用今天叙事解释过去 | 动态叙事标签后续按生效时间入库 |

## 统计与挖掘偏差
| 风险 | 表现 | 控制方式 |
|---|---|---|
| 重叠收益 | 小时级 24h horizon 的 t-stat 虚高 | Newey-West、按天聚合或 block bootstrap |
| 多参数试验 | 只留下成功参数 | 记录所有测试参数和失败记录 |
| 同类因子重复 | 多个因子其实同一暴露 | 计算因子相关性，后续做正交化 |
| 后验改阈值 | 看结果后修改落库规则 | acceptance rule 配置化并带版本 |
| 样本外过短 | 实盘 regime 变化后失效 | OOS、牛熊震荡分段、不同 universe 检查 |

## 每次因子检测建议输出的风险标记
```yaml
data_quality_flags:
  - missing_rate_high
  - stale_price_detected
  - suspicious_volume
  - insufficient_history
  - possible_delisting_bias
  - category_sample_too_small

lookahead_flags:
  - uses_current_universe
  - uses_future_volume
  - category_effective_time_missing
  - funding_time_ambiguous

implementation_flags:
  - high_turnover
  - low_capacity
  - requires_shorting
  - perp_only
  - funding_cost_sensitive
```

## 核心原则
因子检测不是只计算 IC，而是确认这个 IC 是否来自当时可知道、当时可交易、当时可复现的数据条件。
