# 因子计算技术流程细节

## 文档目的
统一记录因子计算流程、实现细节和关键参数，作为代码实现的对齐基线与追踪依据。

## 同步更新规则（强制）
- 任何涉及因子计算逻辑的代码改动（新增、删除、重构、参数调整、默认值变更），都必须同步更新本文件。
- 合并前需检查：代码实现、注释、测试预期与本文件描述一致。

## 当前代码对齐状态（2026-04-25）
- 第一版流程代码已落地并可执行 demo：
  - `src/factor_research/pipeline/*`
  - `src/factor_research/evaluation/*`
  - `src/factor_research/workflow.py`
  - `scripts/run_v1_demo.py`
- 已新增真实数据入库与 DB 驱动执行：
  - `src/factor_research/data/binance_client.py`
  - `src/factor_research/storage/duckdb_store.py`
  - `src/factor_research/runtime/from_db.py`
  - `scripts/ingest_market_data.py`
  - `scripts/run_v1_from_db.py`
- Binance 在部分网络可能返回 `HTTP 451`，客户端自动回退 Coinbase 公共 API。
- 已新增 Agent 挖因子受控执行后端：
  - `src/factor_research/agent_mining/schemas.py`
  - `src/factor_research/agent_mining/formulas.py`
  - `src/factor_research/agent_mining/runner.py`
  - `scripts/run_agent_factor_tasks.py`
  - `configs/agent_factor_tasks.yaml`

## 技术流程基线（待代码实现时逐项落地）
| 步骤 | 目标 | 第一版实现口径 | 待后续调整升级 |
|---|---|---|---|
| 1. Universe 过滤与缺失处理 | 过滤不可交易或样本不足标的，处理缺失值并保留可解释样本 | 多期 `universe_snapshot` 下按 bar 时间匹配最近一次历史快照；当前样例库只有单期快照时走 `single_snapshot_fallback` 并显式标记限制 | 标的池阈值按交易规模、滑点和数据质量校准；补充现货/永续差异 |
| 2. Point-in-time 元数据 | 避免幸存者偏差和未来函数 | 维护 `symbol`、`exchange_symbol`、`coingecko_id`、`listed_time`、`delisted_time`、`tradable_status`、`primary_category`、`category_effective_time` | 后续补充交易对历史、交易暂停、充值提现关闭、数据源回填版本 |
| 3. 分类与标签 | 支持板块中性化、板块内检测和上市时长计算 | 第一版只维护稳定的 `primary_category`，并记录分类生效时间 | 后续引入动态叙事标签，并将 AI/RWA/DePIN/Meme 热度构造成因子 |
| 4. Crypto 数据偏差检查 | 识别容易被忽视的回测偏差 | 检查当前币池回看、下架币删除、交易暂停、代币迁移、交易对切换、标签回看、数据回填 | 后续加入自动化审计报告，标记每次因子检测是否通过 point-in-time 检查 |
| 5. 异常值处理（Winsorize/MAD） | 降低极端值对截面统计和排序结果的扭曲 | 按截面做 winsorize/MAD，再保留处理前后覆盖率记录 | 不同因子使用不同截尾强度；对小币和新币单独设异常规则 |
| 6. 截面标准化（Z-Score/Rank） | 统一量纲，支持跨因子比较和多口径检测 | 默认输出 rank/zscore 两套标准化结果 | 高频因子可增加 robust rank、分组内标准化、缺失值惩罚规则 |
| 7. 风险暴露计算 | 为中性化和诊断提供控制变量 | 第一版计算 `beta`、`size`、`liquidity`、`volatility`、`age`、`primary_category` | 这些变量后续可同时作为独立因子检测；测试某变量时不把自身放入中性化 |
| 8. 中性化（回归残差） | 判断因子是否依赖结构暴露 | `raw` 不剔除；`base_neutral` 剔除 beta/size/liquidity；`strict_neutral` 进一步剔除 volatility/age/primary_category | 中性化变量和阈值配置化；按频率、标的池和因子类型调整 |
| 9. 正交化（残差化或增量正交） | 降低多因子共线性，提升组合解释性 | 第一版只在多因子合成前预留，不作为单因子检测必选项 | 后续支持按因子簇正交、增量 IC 排序正交、避免剔除目标暴露 |
| 10. Horizon 设置 | 对齐预测目标和调仓频率 | 小时级使用 1h/4h/8h/24h/72h；日频使用 1D/3D/7D | 不要求机械单调，要求和因子经济解释一致；资金费率类重点看 8h/24h |
| 11. 评估与回测 | 输出因子预测力和可交易性指标 | 计算 IC/Rank IC、分层收益、多空收益、覆盖率、换手、成本后收益 | 高频统计显著性使用 Newey-West、按天聚合或 block bootstrap 修正自相关 |
| 12. 落库判定 | 结构化记录因子诊断结论 | 第一版状态为 `rejected`、`watchlist`、`research_pass`；阈值写入配置并记录规则版本 | 后续根据实际因子分布调整阈值，增加 `production_candidate` 与组合层验证 |
| 13. Agent 任务受控执行 | 将 Agent 候选转为可复现实验 | 只执行 `approved` 任务；公式必须是白名单 `formula_key + formula_params`；缺字段写入 `blocked` | 后续扩展字段白名单、公式 DSL、相似度去重和样本外滚动验收 |

## Crypto 因子检测偏差清单
| 偏差/风险 | 典型表现 | 第一版控制方式 | 后续升级 |
|---|---|---|---|
| 幸存者偏差 | 只用今天还存在或仍在交易所挂牌的币回测历史 | Universe 按历史时点生成，保留下架前历史 | 补全 delisting 数据源与死亡币样本 |
| 当前成分回看 | 用当前 Top100/Top200 回测过去 | 使用滚动市值/成交额排名生成历史成分 | 建立 point-in-time universe 快照表 |
| 交易所下架/交易暂停 | 下架前暴跌或不可成交阶段被删除 | 记录 `tradable_status` 和 `delisted_time`，不可交易时不允许进入样本 | 区分暂停交易、只读行情、关闭充提、完全下架 |
| 代币迁移/换合约 | old token 与 new token 价格序列错误拼接 | 第一版先记录映射与断点，不自动拼接 | 建立 token migration adjustment 规则 |
| 交易对变更 | 同一币在不同 quote asset 或交易所上的流动性变化被忽略 | 第一版以统一 quote 和交易所范围定义 universe | 后续引入交易对级别可交易性和成交成本 |
| 流动性枯竭 | 历史上虽然有价格但无法有效成交 | 最低成交额/覆盖率/换手约束 | 引入盘口深度、滑点和容量估计 |
| 标签回看 | 用今天的 AI/RWA/DePIN 等标签解释过去 | 第一版只用稳定 `primary_category`，并记录 `category_effective_time` | 动态叙事标签按生效时间入库 |
| 数据源回填 | API 后来修正历史价格、市值、成交量 | 记录数据拉取时间和数据版本 | 建立原始快照和重算版本管理 |
| Funding/合约规则变化 | 资金费率间隔、合约上下架、标记价格规则变化 | 第一版记录市场类型和合约可交易时间 | 后续补充合约规则历史表 |
| 时间戳对齐错误 | 使用未来 K 线收盘价或未来可得市值计算因子 | 因子时间必须早于收益标签起点 | 增加自动化 look-ahead 检查 |

## 第一版因子检测口径
| 检测口径 | 中性化变量 | 用途 |
|---|---|---|
| `raw` | 无 | 观察因子原始预测力 |
| `base_neutral` | `beta`、`size`、`liquidity` | 判断是否只是大盘、小币或流动性暴露 |
| `strict_neutral` | `beta`、`size`、`liquidity`、`volatility`、`age`、`primary_category` | 判断是否更接近独立 alpha |
| `within_category` | 在 `primary_category` 内检测或排名 | 判断是否存在板块内选币能力 |

## 第一版落库样板
| 状态 | 样板标准 | 说明 |
|---|---|---|
| `rejected` | 数据质量不过关，或 raw 口径无稳定信号 | 仍可保留检测记录，便于后续复查 |
| `watchlist` | raw 有信号，但中性化后衰减明显或稳定性不足 | 标记可能的结构暴露，如 liquidity/volatility/category |
| `research_pass` | base_neutral 或 within_category 后仍有稳定信号，且有经济解释 | 进入后续组合模拟或更严格样本外检验 |

## 第一版必须先落地的防偏差能力
| 能力 | 对应数据/配置 | 通过标准 |
|---|---|---|
| Point-in-time universe | `universe_snapshot`、`listed_time`、`delisted_time`、`tradable_status` | 多期快照场景任意 `decision_time` 不使用未来成分；单快照样例库只能作为 smoke test，不作为严格 PIT 研究样本 |
| 数据可得时间 | `event_time`、`available_time`、`ingested_time` | 因子计算满足 `available_time <= decision_time` |
| 可交易状态过滤 | `tradable_status` | 非 `active` 资产不参与当期调仓检测 |
| 分类生效时间 | `category_effective_time` | 分类字段不使用未来标签 |
| 成本后评价 | `fee_cost`、`slippage_cost`、`funding_cost` | 因子报告同时输出毛收益和净收益 |
| 配置版本追踪 | `factor_version`、`test_config_version`、`acceptance_rule_version` | 落库结论可追溯到具体规则版本 |

## 代码路径映射（已落地）
- 因子主流水线：`src/factor_research/pipeline/workflow.py::run_factor_pipeline`
- 预处理模块：`src/factor_research/pipeline/preprocess.py`
- 中性化模块：`src/factor_research/pipeline/neutralize.py::neutralize_ols`
- 正交化模块：`src/factor_research/pipeline/orthogonalize.py`
- V1 流程桥接：`src/factor_research/workflow.py::run_v1_workflow`
- 评估模块：`src/factor_research/evaluation/metrics.py`
- 落库判定：`src/factor_research/evaluation/decision.py::decide_profile`
- 最小验收脚本：`scripts/run_v1_demo.py`
- 真实数据入库：`scripts/ingest_market_data.py`
- DB 驱动执行：`scripts/run_v1_from_db.py`

## 第一版参数实值（当前默认）
- Winsorize：`n_mad=5.0`
- 标准化：`zscore`（支持 `rank` 和 `none`）
- `base_neutral` 暴露：`beta,size,liquidity`
- `strict_neutral` 暴露：`beta,size,liquidity,volatility,age,primary_category`
- OLS 设置：`add_intercept=True`，`min_obs=10`（可配置）
- 正交化：默认关闭（接口已预留）
- within-category：通过 `date + primary_category` 的分组键在组内做截面处理
- 决策状态：`rejected/watchlist/research_pass`（阈值见 `configs/factor_acceptance.yaml`）
- 数据源优先级：Binance 公共 API -> Coinbase 公共 API（fallback）
- DuckDB 表：`market_bars`、`asset_metadata`、`universe_snapshot`、`agent_factor_tasks`、`agent_factor_experiments`、`factor_evaluation`、`factor_decision`
- Universe 过滤：多期 `universe_snapshot` 使用 `bar_time <= snapshot_time` 的历史 as-of 过滤；单期快照时保留 `single_snapshot_fallback`，避免样例库无法执行，但不视为严格 PIT 研究结论。
- Agent 公式白名单：
  - `close_momentum`：按资产计算 `log(close / close.shift(window))`
  - `volume_zscore`：按资产计算成交量滚动 z-score，优先使用 `quote_volume` 或 `volume`
  - `volatility`：按资产计算收益率滚动标准差
- Agent 方向处理：`direction=negative` 时对公式输出取反；`positive` 保持原值。
- Agent 执行状态：`approved` 进入执行；`draft/rejected/executed/blocked/failed` 不进入 pipeline，记录为 skipped 或对应失败状态。

## 变更记录
- 2026-04-25：新增 Agent 因子任务受控执行、白名单公式、approved-only 调度和实验/评估/判定落库。
- 2026-04-25：补齐多期 universe snapshot 的 as-of 过滤路径，并明确单期样例库 fallback 限制。
- 2026-04-24：新增真实数据接入、DuckDB 落库、DB 驱动流程与 API fallback 机制。
- 2026-04-24：落地第一版代码骨架与可执行 demo，补齐代码路径映射与参数实值。
- 2026-04-24：补充 point-in-time universe、幸存者偏差与 Crypto 特有数据偏差清单。
- 2026-04-24：补充因子检测口径、落库样板，以及待后续调整升级的技术细节。
- 2026-04-24：初始化文档，建立强制同步规则与流程基线。
