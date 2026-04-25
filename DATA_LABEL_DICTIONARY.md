# 数据标签与字段字典

## 文档目的
统一解释因子检测系统中的英文 key、中文含义、字段用途和数据结构，避免后续实现时字段口径混乱。

## 核心命名规则
| 规则 | 说明 |
|---|---|
| 时间字段统一使用 `_time` | 表示具体时间点，例如 `event_time`、`listed_time` |
| 状态字段统一使用 `_status` | 表示枚举状态，例如 `tradable_status`、`decision_status` |
| 分类字段使用 `category` 或 `tag` | `category` 偏稳定主分类，`tag` 偏多标签或动态标签 |
| 配置版本使用 `_version` | 用于追踪回测和落库规则变化 |
| 布尔字段使用 `is_` 或 `has_` | 例如 `is_tradable`、`has_forward_label` |

## 资产元数据：`asset_metadata`
| 字段 | 中文名 | 含义 | 示例 |
|---|---|---|---|
| `asset_id` | 资产唯一 ID | 系统内部稳定 ID，不随交易所 symbol 变化 | `asset_btc` |
| `symbol` | 通用代码 | 市场常用代码 | `BTC` |
| `exchange_symbol` | 交易所代码 | 某交易所实际交易代码 | `BTCUSDT` |
| `coingecko_id` | CoinGecko ID | 用于关联外部元数据 | `bitcoin` |
| `market_type` | 市场类型 | `spot` 或 `perpetual` | `perpetual` |
| `exchange` | 交易所 | 数据来源或可交易场所 | `binance` |
| `quote_asset` | 计价资产 | 交易对计价币 | `USDT` |
| `listed_time` | 上市时间 | 该资产/交易对可交易起点 | `2021-01-01 00:00:00` |
| `delisted_time` | 下架时间 | 下架或不可交易时间，未下架为空 | `<null>` |
| `tradable_status` | 可交易状态 | 当前或历史时点交易状态 | `active` |
| `primary_category` | 主分类 | 稳定板块分类，用于中性化和板块内检测 | `L1` |
| `category_effective_time` | 分类生效时间 | 该分类在何时可被认为已知 | `2021-01-01 00:00:00` |
| `metadata_source` | 元数据来源 | 标签和上市信息来源 | `coingecko` |
| `metadata_version` | 元数据版本 | 追踪元数据修订 | `v0.1` |

## 可交易状态：`tradable_status`
| 值 | 中文含义 | 处理方式 |
|---|---|---|
| `active` | 正常交易 | 可进入 universe |
| `suspended` | 暂停交易 | 不允许调仓成交 |
| `delisted` | 已下架 | 下架后不进入 universe |
| `listing_pending` | 待上市 | 不进入 universe |
| `maintenance` | 交易维护 | 不允许调仓成交 |
| `unknown` | 状态未知 | 默认不进入严格回测，或标记风险 |

## 主分类：`primary_category`
| 值 | 中文名 | 含义 |
|---|---|---|
| `BTC` | 比特币 | BTC 本身或强 BTC 原生资产 |
| `L1` | 一层公链 | 通用智能合约或基础公链 |
| `L2` | 二层扩容 | 以太坊或其他生态扩容网络 |
| `DeFi` | 去中心化金融 | 借贷、DEX、衍生品、收益协议等 |
| `CEX` | 交易所平台币 | 中心化交易所相关代币 |
| `Meme` | Meme/社区币 | 主要由社区和情绪驱动 |
| `Gaming` | 游戏/NFT 游戏 | GameFi、链游、游戏生态 |
| `Infrastructure` | 基础设施 | Oracle、Storage、Bridge、DePIN、开发工具等 |
| `Stablecoin_Related` | 稳定币相关 | 稳定币协议、CDP、收益型稳定币 |
| `Other` | 其他 | 样本不足或暂无法归类 |

## Universe 快照：`universe_snapshot`
| 字段 | 中文名 | 含义 |
|---|---|---|
| `snapshot_time` | 快照时间 | universe 生效时间 |
| `universe_name` | 标的池名称 | 例如 `rolling_top_200` |
| `asset_id` | 资产唯一 ID | 关联资产元数据 |
| `rank_metric` | 排名指标 | `market_cap`、`quote_volume` 等 |
| `rank_value` | 排名指标值 | 当时可见的指标值 |
| `rank_number` | 排名 | 当时在 universe 中的排名 |
| `is_member` | 是否入池 | 是否进入该时点标的池 |
| `exclude_reason` | 剔除原因 | 流动性不足、未上市、已下架等 |
| `config_version` | 配置版本 | universe 规则版本 |

## 行情数据：`market_bars`
| 字段 | 中文名 | 含义 |
|---|---|---|
| `event_time` | K 线时间 | K 线对应市场时间 |
| `available_time` | 可用时间 | 系统可使用该 K 线的时间 |
| `asset_id` | 资产唯一 ID | 关联资产 |
| `open` | 开盘价 | K 线开盘价 |
| `high` | 最高价 | K 线最高价 |
| `low` | 最低价 | K 线最低价 |
| `close` | 收盘价 | K 线收盘价 |
| `volume_base` | 基础币成交量 | 以 base asset 计量 |
| `volume_quote` | 计价币成交额 | 以 quote asset 计量 |
| `price_type` | 价格类型 | `last`、`mark`、`index`、`mid` |
| `data_source` | 数据来源 | 交易所或 API |
| `ingested_time` | 入库时间 | 本地拉取入库时间 |

## 风险暴露：`factor_exposures`
| 字段 | 中文名 | 含义 |
|---|---|---|
| `exposure_time` | 暴露时间 | 暴露值生效时间 |
| `asset_id` | 资产唯一 ID | 关联资产 |
| `beta` | 市场 Beta | 相对市场或 BTC/ETH 的收益敏感度 |
| `size` | 规模 | 通常用市值或流通市值代理 |
| `liquidity` | 流动性 | 成交额、换手或盘口深度代理 |
| `volatility` | 波动率 | 滚动收益波动 |
| `age` | 上市时长 | 当前时间减上市时间 |
| `primary_category` | 主分类 | 稳定板块分类 |
| `calc_config_version` | 计算配置版本 | 暴露计算规则版本 |

## 因子值：`factor_values`
| 字段 | 中文名 | 含义 |
|---|---|---|
| `factor_time` | 因子时间 | 因子可用于决策的时间 |
| `asset_id` | 资产唯一 ID | 关联资产 |
| `factor_id` | 因子 ID | 因子唯一标识 |
| `factor_name` | 因子名称 | 可读名称 |
| `raw_value` | 原始因子值 | 未处理信号 |
| `winsorized_value` | 去极值后值 | 异常值处理后 |
| `zscore_value` | Z 分数 | 截面标准化值 |
| `rank_value` | 排名分数 | 截面 rank 或 percentile |
| `neutralized_value` | 中性化后值 | 回归残差或剔除暴露后值 |
| `factor_version` | 因子版本 | 因子定义版本 |

## 检测口径：`factor_test_profile`
| 字段/值 | 中文名 | 含义 |
|---|---|---|
| `raw` | 原始口径 | 不做中性化 |
| `base_neutral` | 基础中性 | 剔除 `beta`、`size`、`liquidity` |
| `strict_neutral` | 严格中性 | 进一步剔除 `volatility`、`age`、`primary_category` |
| `within_category` | 板块内检测 | 在 `primary_category` 内排名或检测 |
| `test_config_version` | 检测配置版本 | 记录检测口径版本 |

## 收益标签：`forward_returns`
| 字段 | 中文名 | 含义 |
|---|---|---|
| `label_start_time` | 标签起点 | forward return 开始时间 |
| `label_end_time` | 标签终点 | forward return 结束时间 |
| `horizon` | 预测周期 | `1h`、`4h`、`8h`、`24h`、`72h` 等 |
| `asset_id` | 资产唯一 ID | 关联资产 |
| `gross_return` | 毛收益 | 未扣成本收益 |
| `net_return` | 净收益 | 扣除成本后的收益 |
| `fee_cost` | 手续费 | 交易手续费估计 |
| `slippage_cost` | 滑点成本 | 成交冲击估计 |
| `funding_cost` | 资金费率成本 | 永续合约资金费率影响 |

## 因子评估结果：`factor_evaluation`
| 字段 | 中文名 | 含义 |
|---|---|---|
| `factor_id` | 因子 ID | 被检测因子 |
| `profile_name` | 检测口径 | `raw`、`base_neutral` 等 |
| `universe_name` | 标的池 | 检测使用 universe |
| `horizon` | 预测周期 | 收益标签周期 |
| `rank_ic_mean` | Rank IC 均值 | 截面秩相关均值 |
| `rank_ic_tstat` | Rank IC t 值 | 显著性指标，小时级需修正自相关 |
| `ic_positive_ratio` | IC 正向比例 | IC 方向稳定性 |
| `long_short_return` | 多空收益 | Top-Bottom 收益 |
| `turnover` | 换手率 | 因子组合换手 |
| `coverage_ratio` | 覆盖率 | 有效样本比例 |
| `cost_adjusted_return` | 成本后收益 | 扣成本后的收益表现 |

## 落库决策：`factor_decision`
| 字段/值 | 中文名 | 含义 |
|---|---|---|
| `rejected` | 拒绝 | 数据质量差或无稳定信号 |
| `watchlist` | 观察 | 有信号但证据不足 |
| `research_pass` | 研究通过 | 值得进入后续组合模拟 |
| `decision_status` | 决策状态 | 上述状态之一 |
| `alpha_type` | 收益来源类型 | `pure_alpha`、`risk_premium`、`category_rotation` 等 |
| `passed_profiles` | 通过口径 | 哪些检测口径通过 |
| `failed_profiles` | 失败口径 | 哪些检测口径失效 |
| `risk_flags` | 风险标记 | 数据、未来函数、执行风险等 |
| `acceptance_rule_version` | 落库规则版本 | 判断标准版本 |

## 风险标记：`risk_flags`
| 标记 | 中文含义 | 说明 |
|---|---|---|
| `missing_rate_high` | 缺失率高 | 因子或行情覆盖不足 |
| `stale_price_detected` | 价格停滞 | 可能存在不可交易或坏数据 |
| `suspicious_volume` | 可疑成交量 | 可能有刷量或数据异常 |
| `insufficient_history` | 历史不足 | 新币或数据样本太短 |
| `possible_delisting_bias` | 可能下架偏差 | 下架/失败样本覆盖不足 |
| `category_sample_too_small` | 板块样本太少 | 板块内检测不稳定 |
| `uses_current_universe` | 使用当前币池 | 明显未来函数风险 |
| `uses_future_volume` | 使用未来成交额 | universe 筛选未来函数 |
| `category_effective_time_missing` | 分类生效时间缺失 | 可能标签回看 |
| `funding_time_ambiguous` | 资金费率时间不清 | funding 因子时间错位风险 |
| `high_turnover` | 高换手 | 成本敏感 |
| `low_capacity` | 容量低 | 小币或流动性不足 |
| `requires_shorting` | 需要做空 | 现货不可直接实现 |
| `perp_only` | 仅永续可交易 | 依赖合约市场 |
| `funding_cost_sensitive` | 对资金费率敏感 | 永续多空收益需谨慎 |

## 建议的数据流
```text
asset_metadata + market_bars -> universe_snapshot
market_bars + asset_metadata -> factor_exposures
market_bars -> factor_values
factor_values + factor_exposures + universe_snapshot -> factor_test_profile results
market_bars -> forward_returns
profile results + forward_returns -> factor_evaluation
factor_evaluation + risk_flags + acceptance rules -> factor_decision
```
