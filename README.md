# Crypto Factor Research Project

## 项目简介
分钟级 Crypto 截面多因子研究系统（研究闭环版本）。当前核心是可控因子检测链路，下一阶段升级为 Agent 辅助挖因子闭环：Agent 生成候选任务，人工确认后由系统受控执行和评估。

## 技术栈
- 研究引擎：Python（pandas / numpy / pyyaml）
- 存储：DuckDB + Parquet
- 当前 UI 原型：Streamlit（最小可用版，用于研究联调和 DuckDB smoke test）
- 目标前端：Next.js App Router + React + TypeScript + Tailwind CSS
- 前后端边界：Next.js 负责产品化 UI；Python/FastAPI 或受控 API 层负责 DuckDB 读取、Agent 任务执行和因子研究流水线

## 本地运行
1. 使用项目 Python 环境：
   - `C:\Users\hp\anaconda3\envs\mt5\python.exe`
2. 安装依赖（推荐）：
   - `& "C:\Users\hp\anaconda3\envs\mt5\python.exe" -m pip install duckdb streamlit`
   - 国内镜像（建议优先）：`& "C:\Users\hp\anaconda3\envs\mt5\python.exe" -m pip install -i http://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com duckdb streamlit`
   - 若超过约 2 分钟无下载进度，立即切换镜像或切换安装路径（不要长时间等待）。
3. 运行第一版流程 Demo（mock 数据）：
   - `& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/run_v1_demo.py`
4. 拉取真实行情并入库 DuckDB：
   - `& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/ingest_market_data.py --db-path data/factor_research.duckdb --limit-symbols 12 --start-time 2026-04-20T00:00:00Z --end-time 2026-04-24T00:00:00Z`
5. 基于数据库运行流程：
   - `& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/run_v1_from_db.py --db-path data/factor_research.duckdb --horizon-hours 8`
6. 执行 Agent 因子任务（只运行 `approved` 任务）：
   - `& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/run_agent_factor_tasks.py --db-path data/factor_research.duckdb --tasks configs/agent_factor_tasks.yaml --horizon-hours 8`
   - 若 `mt5` 环境缺少 DuckDB，可用当前本地兜底依赖：`$env:PYTHONPATH="C:\Users\hp\work\crypto-factor-research-project\.tmp\pydeps"; & "C:\Users\hp\anaconda3\python.exe" scripts/run_agent_factor_tasks.py --db-path data/factor_research.duckdb --tasks configs/agent_factor_tasks.yaml --horizon-hours 8`
7. 启动 UI：
   - 推荐：`& "C:\Users\hp\anaconda3\python.exe" scripts/start_ui.py`
   - Windows 独立控制台保活：`scripts\start_ui.cmd`
   - 仅当 `mt5` 环境已安装 Streamlit/DuckDB 时：`& "C:\Users\hp\anaconda3\envs\mt5\python.exe" -m streamlit run ui/app.py`

## 依赖安装故障处理（Windows）
- 现象：`pip install` 长时间停在 `Looking in indexes` 或反复超时。  
  处理：改用国内镜像（如阿里云），并设置 `--trusted-host`。
- 现象：`--user` 安装出现权限错误（如 `WinError 183` / `Errno 13 Permission denied`）。  
  处理：安装到项目本地目录并通过 `PYTHONPATH` 启动。

示例（项目本地依赖目录）：
```powershell
$deps="C:\Users\hp\work\crypto-factor-research-project\.tmp\pydeps"
New-Item -ItemType Directory -Force -Path $deps | Out-Null
& "C:\Users\hp\anaconda3\python.exe" -m pip install --no-deps --target $deps .\.tmp\duckdb-1.5.2-cp312-cp312-win_amd64.whl
$env:PYTHONPATH=$deps
& "C:\Users\hp\anaconda3\python.exe" -m streamlit run ui/app.py
```

## 常用命令
- 运行 Demo：`& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/run_v1_demo.py`
- 真实数据入库：`& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/ingest_market_data.py --db-path data/factor_research.duckdb --limit-symbols 12`
- DB 驱动流程：`& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/run_v1_from_db.py --db-path data/factor_research.duckdb --horizon-hours 8`
- Agent 因子任务：`& "C:\Users\hp\anaconda3\envs\mt5\python.exe" scripts/run_agent_factor_tasks.py --db-path data/factor_research.duckdb --tasks configs/agent_factor_tasks.yaml --horizon-hours 8`
- UI：`& "C:\Users\hp\anaconda3\python.exe" scripts/start_ui.py`
- 加载配置：`configs/factor_test_profiles.yaml`、`configs/factor_acceptance.yaml`、`configs/agent_factor_tasks.yaml`

## 目录结构
- `README.md`：项目整体说明与使用入口
- `ARCHITECTURE.md`：模块职责、调用关系与设计约束
- `CONTEXT.md`：当前进展、关键决策与下一步
- `FACTOR_CALC_TECH_DETAIL.md`：因子计算技术流程细节（与代码实现对齐）
- `FACTOR_RESEARCH_NOTES.md`：因子研究注意事项与偏差检查清单
- `DATA_LABEL_DICTIONARY.md`：数据标签、字段结构与中文解释
- `AGENT_FACTOR_MINING_ROADMAP.md`：Agent 因子挖掘长期路线方案
- `UI_DESIGN_GUIDE.md`：Agent 挖因子系统 UI 视觉基准、页面体系和用户流程
- `FRONTEND_MIGRATION_PLAN.md`：从 Streamlit 原型迁移到 Next.js 前端的技术栈和分阶段更新方案
- `PROJECT_TASK_ARCHIVE.md`：当前项目任务拆分、优先级、阶段顺序和后续接手入口
- `UI_AGENT_ORCHESTRATION_TEMPLATE.md`：GPT-5.5 调度 Build Web Apps / Browser Use / GPT-5.3 Sub-Agents 的 UI 任务拆分模板
- `src/factor_research/models`：核心数据结构定义
- `src/factor_research/config`：检测口径与配置加载
- `src/factor_research/pipeline`：预处理/中性化/正交化/流程编排
- `src/factor_research/evaluation`：评估指标与决策逻辑
- `src/factor_research/workflow.py`：第一版流程总入口
- `src/factor_research/data`：交易所公共 API 客户端（Binance 优先，失败回退 Coinbase）
- `src/factor_research/storage`：DuckDB 建表与幂等入库
- `src/factor_research/runtime`：基于 DuckDB 的流程运行入口
- `src/factor_research/agent_mining`：Agent 因子任务校验、受控公式执行、approved-only 调度和实验摘要
- `scripts/run_v1_demo.py`：最小可运行验收脚本
- `scripts/ingest_market_data.py`：真实行情入库脚本
- `scripts/run_v1_from_db.py`：DB 驱动评估脚本
- `scripts/run_agent_factor_tasks.py`：Agent 因子任务执行脚本
- `scripts/start_ui.py` / `scripts/start_ui.cmd`：UI 启动脚本（自动加载 `.tmp/pydeps`）
- `configs/`：第一版 profile 与 acceptance 规则配置
- `ui/app.py`：最小可用 Streamlit 页面，保留为研究原型和数据联调入口
- `ui/agent_factor_ui_overview.png`：后续 UI 生成和重设计的唯一 Ultra HD 总览参考图

## 协作执行约定
- 默认情况下，非微小任务会先做并行拆分并分配 sub agent 执行（数据层、流程层、UI/文档层等）。
- 主线程负责收敛、联调、验收和 code review。
- 只有在高风险操作、权限升级或需求关键歧义时才暂停确认。
- UI 系统任务默认采用 `UI_AGENT_ORCHESTRATION_TEMPLATE.md`：GPT-5.5 负责 Build Web Apps 设计契约、任务拆分、Browser Use 验收和最终收敛；GPT-5.3 Sub-Agents 负责边界清晰的代码分片。

## 实施方案
| 阶段 | 目标 | 主要内容 | 当前取舍 |
|---|---|---|---|
| 1. 文档与口径基线 | 明确第一版研究边界 | 维护 README/ARCHITECTURE/CONTEXT/FACTOR_CALC_TECH_DETAIL | 当前只做因子检测系统，不做完整交易策略系统 |
| 2. 元数据与标的池 | 建立 point-in-time 资产基础信息 | `symbol`、`coingecko_id`、`listed_date`、`delisted_date`、`tradable_status`、`primary_category`、滚动 Top100/Top200 标的池 | 第一版只维护稳定的 `primary_category`，但必须避免用当前币池回看历史 |
| 3. 数据偏差控制 | 降低幸存者偏差与未来函数 | 上市/下架、交易暂停、交易对变更、代币迁移、标签生效时间、数据回填记录 | 第一版先记录必要元数据和风险检查，复杂修正后续升级 |
| 4. 风险暴露变量 | 支持中性化和诊断 | `beta`、`size`、`liquidity`、`volatility`、`age`、`primary_category` | 第一版默认作为 exposures/controls；后续也可注册为因子检测 |
| 5. 因子检测口径 | 判断因子收益来源 | `raw`、`base_neutral`、`strict_neutral`、`within_category` | 用检测口径替代复杂策略模板，避免过早抽象 |
| 6. 因子评估与落库 | 结构化记录检测结论 | IC/Rank IC、分层收益、多空收益、覆盖率、换手、成本后表现、决策状态 | 第一版只做 `rejected/watchlist/research_pass`，阈值配置化并带版本 |
| 7. Agent 挖因子第一版 | 提高研究想法生成和实验复盘效率 | 结构化任务模板、人工确认、公式白名单、实验记忆、Agent 复盘摘要 | 不训练 RL，不执行任意 Python，不自动入生产 |
| 8. Next.js 前端升级 | 从 Streamlit 原型走向产品化工作台 | Next.js + React + TypeScript + Tailwind、Python API、真实任务/实验/评估数据接入 | Streamlit 仅保留为研究联调入口，详细方案见 `FRONTEND_MIGRATION_PLAN.md` |
| 9. 后续升级 | 从检测走向组合研究 | 叙事因子、组合模拟、成本模型、生产候选标准、Web 展示 | 在因子检测和 Agent 任务闭环稳定后再扩展 |

## Agent 挖因子升级方案
第一版目标链路：

```text
1 提出目标
-> 2 Agent 拆解任务
-> 3 拉取数据
-> 4 生成候选因子
-> 5 批量回测
-> 6 人工审核
-> 7 入库/组合
-> 8 监控迭代
```

核心取舍：
- Agent 只负责提出假设、公式草案和复盘，不负责最终裁判。
- 只有 `approved` 任务会执行；`draft/rejected/blocked/executed/failed` 不进入 pipeline。
- 自由文本公式不直接执行，必须映射到受控 `formula_key`。
- 当前只有 OHLCV 数据可直接执行；funding、OI、爆仓、盘口类任务先记录为待接入数据。
- UI 交互和后端状态机必须按上述用户流程对齐；视觉与页面结构参考 `UI_DESIGN_GUIDE.md`。
- 详细方案见 `AGENT_FACTOR_MINING_ROADMAP.md` 的“当前系统升级执行方案”。

## 文档维护要求
- 每次阶段性任务完成后必须更新 `CONTEXT.md`。
- 当功能、运行方式、命令、依赖或使用方式发生明显变化时更新 `README.md`。
- 当模块划分、调用关系、边界职责或关键设计决策发生变化时更新 `ARCHITECTURE.md`。
- **当任意因子计算相关代码发生变更时，必须同步更新 `FACTOR_CALC_TECH_DETAIL.md`，确保文档与代码细节一致，便于后续追踪。**
