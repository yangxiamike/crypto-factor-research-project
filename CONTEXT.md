# CONTEXT

## 当前在做
已完成 Agent 挖因子新方案后端第一版闭环：结构化任务校验、公式白名单、approved-only 执行、字段缺失 blocked、实验/评估/判定落库和脚本验收。当前在做项目任务拆分归档，为 Next.js 前端迁移和后续 Agent 挖因子工作台开发建立接手入口。

## 上次做到哪里
已完成第一版因子检测代码骨架、配置、真实数据入库、DB 驱动流程和 Agent 挖因子后端受控执行链路；UI 已从最小可用界面向 `ui/agent_factor_ui_overview.png` 收敛。

## 最近关键决定
- 新增 `AGENT_FACTOR_MINING_ROADMAP.md`，作为后续 Agent 挖因子系统的路线方案文档。
- Agent 挖因子路线采用分阶段推进：先让 Agent 做研究助理，再做半自动研究循环，最后再考虑搜索/RL 自进化。
- 第一版不训练 RL，不让 Agent 直接执行任意 Python；先输出结构化因子任务，由人确认后交给现有因子检测系统。
- RL/搜索算法后期定位为“提高搜索效率的模块”，不是因子好坏的裁判；裁判仍是 IC、Rank IC、分层收益、成本后收益、稳定性、去相关和样本外表现。
- 并行拆分开发：数据模型/配置、流水线核心、评估与 demo 三条子任务。
- 新增 `src/factor_research` 代码骨架，完成预处理、中性化、正交化、评估和决策模块。
- 新增 `configs/factor_test_profiles.yaml` 与 `configs/factor_acceptance.yaml`。
- 增加 `run_v1_workflow` 作为第一版流程入口，打通 profile 配置到 pipeline 的桥接。
- 修复集成问题：`categorical_cols` 与暴露列不一致导致报错。
- 修复行为问题：`within_category` 改为按 `date + primary_category` 分组截面处理。
- 修复可读性问题：决策失败原因去重。
- 文档同步策略继续生效：代码变更必须同步 `FACTOR_CALC_TECH_DETAIL.md`。
- 新增真实数据接入与落库：
  - `scripts/ingest_market_data.py`
  - `src/factor_research/data/binance_client.py`
  - `src/factor_research/storage/duckdb_store.py`
- 新增数据库驱动流程：
  - `scripts/run_v1_from_db.py`
  - `src/factor_research/runtime/from_db.py`
- 新增最小可用 UI：`ui/app.py`（直连 DuckDB）
- 数据源策略调整为：Binance 优先，遇到 `HTTP 451` 自动回退 Coinbase 公共 API。
- 协作机制写入文档：默认对非微小任务先并行分配 sub agent，主线程做收敛与 code review。
- 依赖安装执行策略更新：`pip` 长时间无进度时应快速切换国内镜像或安装路径，不做长时间等待。
- 在当前权限受限环境下采用“项目本地依赖目录（`.tmp/pydeps`）+ `PYTHONPATH`”作为 UI 兜底启动方案。
- 常规 `mt5` 环境缺少 `streamlit`；UI 当前使用 Anaconda base Python + `.tmp/pydeps` 中的 DuckDB 启动。
- 新增 `scripts/start_ui.py` 与 `scripts/start_ui.cmd`：前者在进程内加载 `.tmp/pydeps` 后启动 Streamlit，后者用于 Windows 独立控制台保活。
- 已用 browser 打开 `http://127.0.0.1:8501` 验证 UI 可加载 DuckDB、展示 `market_bars` 折线图；本轮后端已落库 `factor_evaluation` / `factor_decision`，后续 UI 可接入真实评估结果。
- 已明确 Agent 挖因子第一版升级方案：
  - Agent 输出结构化候选任务，不直接执行代码。
  - 人工确认后，只有 `approved` 任务进入执行。
  - 自由文本公式必须映射为 `formula_key + formula_params`，由公式白名单执行。
  - 复用现有 `raw/base_neutral/strict_neutral/within_category` 检测口径。
  - 新增实验记忆表，记录任务、实验、评估、判定和风险标签。
  - funding、OI、爆仓、盘口等字段缺失时，任务标记为 `blocked`，等待数据源接入。
- 已替换 `ui/agent_factor_ui_overview.png` 为 7680×4320 Ultra HD 总览图，覆盖 10 个页面、组件、字体、图标、状态和 8 步使用流程。
- 已删除旧 `ui/agent_factor_ui_overview_4x.png`，后续不再维护派生高清图，避免视觉基准分叉。
- 已新增 `UI_DESIGN_GUIDE.md`，固化浅色圆润卡通风、页面体系、交互图标、字体和 8 步用户流程。
- 已按新要求使用 `imagegen` 重新生成 `ui/agent_factor_ui_overview.png`，采用浅色、圆润、治愈系卡通风，不复用之前 UI 设计总览图。
- 已删除历史 UI 参考图 `ui/ui_reference.png`，避免后续实现误用旧视觉方案。
- 新总览图包含核心 `Agent 挖因子` 工作台、10 个页面缩略图、8 步用户流程、交互图标库、字体规范和状态标签，后续系统方案与该图对齐。
- Agent 挖因子修改方案已从后端流水线表达调整为用户流程表达：提出目标、Agent 拆解、拉取数据、生成候选、批量回测、人工审核、入库/组合、监控迭代。
- 前端页面体系按 `总览驾驶舱`、`Agent 挖因子`、`因子实验室`、`回测与归因`、`因子库`、`数据地图`、`组合工作台`、`报告中心`、`监控与告警`、`设置` 组织。
- 新增 `UI_AGENT_ORCHESTRATION_TEMPLATE.md`，作为 UI 系统任务拆分和多模型调度模板。
- UI 系统任务默认由 GPT-5.5 负责主调度、Build Web Apps 设计契约和 Browser Use 验收；GPT-5.3 Sub-Agents 只负责边界清晰、写入范围互斥的代码分片。
- 本轮 UI 收敛已采用两个 GPT-5.3 Sub-Agent 分片：
  - `ui/agent_ui_style.py`：强化浅色纸张背景、圆润卡片、状态芯片、按钮、tab、表格、进度条和可复用贴纸/图标 helper。
  - `ui/agent_ui_data.py`：补齐顶部状态芯片、候选池统计、因子库表、数据地图覆盖数、图标库、字体规范和后续系统提示 seed。
- 主线程已更新 `ui/app.py`：新增顶部总览 banner、全局状态芯片、10 页面缩略图、8 步流程条、主 Agent 工作台、右侧数据验证/因子库快照，并接入新增 seed 字段。
- Browser Use 已验证 `http://127.0.0.1:8501` 可加载新 UI，控制台无 error/warning；已修复顶部状态芯片因 Markdown 缩进被渲染为代码块的问题。
- Agent 挖因子后端已新增 `src/factor_research/agent_mining`：
  - `schemas.py`：结构化任务读取与校验。
  - `formulas.py`：白名单公式 `close_momentum`、`volume_zscore`、`volatility`。
  - `runner.py`：approved-only 执行、字段检查、profile/horizon 循环、实验摘要和 DuckDB 落库。
- 新增 `scripts/run_agent_factor_tasks.py` 与 `configs/agent_factor_tasks.yaml`，示例覆盖 executed、skipped、blocked 三类状态。
- DuckDB 新增表：`agent_factor_tasks`、`agent_factor_experiments`、`factor_evaluation`、`factor_decision`。
- 修复 `universe_snapshot` 成分列识别：DB 流程现在同时支持 `is_member` 和现有 `is_in_universe`。
- 修复 universe 口径与文档不一致问题：当 `universe_snapshot` 存在多期快照时，DB 流程和 Agent 流程按 bar 时间匹配最近一次历史快照；当前样例库只有单期快照，仍走显式 `single_snapshot_fallback`。
- 本轮脚本验收结果：approved 的 `close_momentum_w24` 跑通 2 个 horizon × 4 个 profile；draft 任务 skipped；缺 `funding_rate` 任务 blocked；`factor_evaluation` 与 `factor_decision` 已落库。
- 本轮 Browser Use 对照检查：已用 Anaconda base Python 启动 Streamlit，当前页面可在 `http://127.0.0.1:8501` 渲染，截图保存到 `.tmp/current_ui_browseruse_fullpage.png`；浏览器控制台无 error/warning。当前 in-app browser 视口较窄，UI 呈纵向堆叠，与超宽基准图差异主要集中在横向总览结构、主工作台比例、卡通贴纸/图标真实度和右侧规范区完整度。
- 前端技术栈决策更新：Streamlit 保留为研究原型和 DuckDB 联调入口；目标前端切换为 Next.js App Router + React + TypeScript + Tailwind CSS，后端研究计算继续由 Python/DuckDB/Agent 任务链路承担。
- 新增 `FRONTEND_MIGRATION_PLAN.md`：记录 Next.js 目标目录、API 边界、Streamlit 定位和阶段 0-5 的更新方案。
- 已同步更新 `README.md`、`ARCHITECTURE.md`、`UI_DESIGN_GUIDE.md`、`UI_AGENT_ORCHESTRATION_TEMPLATE.md`，统一新前端技术栈口径和后续 UI 分片写入范围。
- 新增 `PROJECT_TASK_ARCHIVE.md`：按数据与存储、因子研究引擎、Agent 挖因子、Next.js 前端、视觉资产、API、测试、文档治理拆分任务，记录优先级、阶段顺序、Sub-Agent 分片和下一次启动建议。

## 当前阻塞
- 尚未建立自动化测试（目前是脚本级最小验收）。
- `mt5` 环境当前缺少 DuckDB；Agent 脚本可用 Anaconda base Python + `.tmp/pydeps` 兜底运行，或后续给 `mt5` 安装 DuckDB。
- funding、OI、爆仓、盘口等字段仍未接入，相关 Agent 任务会按设计进入 `blocked`。
- Browser Use 当前 IAB 视口较窄，侧栏会折叠；本轮已完成窄视口加载和核心交互验证，但还需要在 Next.js 前端骨架完成后做宽桌面视口视觉对照。
- Next.js 前端尚未初始化，当前运行入口仍是 Streamlit。

## 下一步
- 下一步初始化 `frontend/`：Next.js App Router + React + TypeScript + Tailwind CSS，先用 seed 数据还原基准图的横向工作台结构。
- 后续任务接手优先读 `PROJECT_TASK_ARCHIVE.md` 和 `FRONTEND_MIGRATION_PLAN.md`，再进入具体实现。
- 后续继续按 `UI_AGENT_ORCHESTRATION_TEMPLATE.md` 拆分 UI 分片，由 GPT-5.5 统一浏览器验收和文档收敛。
- 后续 UI 开发统一以 `ui/agent_factor_ui_overview.png` 为唯一参考，不再额外维护历史参考图、派生子图或 4x 图，避免视觉口径分叉。
- 下一轮 UI 微调重点迁移到 Next.js：桌面宽视口下对齐基准图的横向主工作台比例、侧边页面缩略图密度、卡通助手贴纸位置和右侧图标/字体规范区。
- 为 `agent_mining` 补 pytest：任务校验、非 approved 跳过、缺字段 blocked、白名单公式、落库结果。
- 在 UI 中从真实 `agent_factor_tasks` / `agent_factor_experiments` / `factor_evaluation` 读取任务和结果，替换部分 seed 数据。
- 将 acceptance 规则与 profile 参数进一步配置化（按 frequency/universe/factor_type 分层）。
- 增加自动化测试：preprocess、neutralize、workflow、decision 的单测与集成测试。
- 引入 point-in-time 审计检查（available_time <= decision_time）并落库风险标记。
- 将“镜像切换 + 本地依赖目录兜底”进一步封装为依赖安装脚本，减少手工排障时间。
