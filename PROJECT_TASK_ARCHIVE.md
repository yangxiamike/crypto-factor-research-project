# PROJECT_TASK_ARCHIVE

## 归档时间

2026-04-25

## 当前项目状态

项目已完成第一版后端研究闭环和 Agent 挖因子受控执行链路：

- 因子检测 pipeline 已具备预处理、中性化、正交化、评估和判定。
- DuckDB 已能落库行情、元数据、universe、Agent 任务、实验、评估和决策。
- Agent 任务执行已支持 `approved-only`、公式白名单、字段缺失 `blocked`、实验摘要落库。
- 当前 UI 仍是 Streamlit 原型；目标前端已决策切换到 Next.js App Router + React + TypeScript + Tailwind CSS。

## 总目标拆分

```text
目标：Agent 辅助 Crypto 因子研究工作台

1. 数据与存储
2. 因子研究引擎
3. Agent 挖因子受控链路
4. Next.js 产品化前端
5. 图片与视觉资产
6. API 与前后端联调
7. 测试与验收
8. 文档与项目治理
```

## 任务总览

| 编号 | 模块 | 状态 | 优先级 | 目标 |
|---|---|---|---|---|
| T01 | 后端研究闭环 | 已完成第一版 | P0 | 保持 pipeline、evaluation、decision 可跑通 |
| T02 | Agent 挖因子后端 | 已完成第一版 | P0 | 受控执行 approved 任务并落库 |
| T03 | Next.js 前端骨架 | 待开始 | P0 | 初始化 `frontend/` 并建立页面路由和布局 |
| T04 | UI 视觉资产 | 待开始 | P0 | 生成并整理 mascot、贴纸、插画、空状态资源 |
| T05 | 基准图还原 | 待开始 | P0 | 用 Next.js 还原 `ui/agent_factor_ui_overview.png` 的横向工作台 |
| T06 | Python API 层 | 待开始 | P0 | 为前端提供任务、实验、评估、数据覆盖接口 |
| T07 | 前端真实数据接入 | 待开始 | P1 | 用真实 DuckDB 数据替换 seed 数据 |
| T08 | 受控操作闭环 | 待开始 | P1 | 支持审核、拒绝、执行 approved 任务 |
| T09 | 数据源扩展 | 待开始 | P1 | 接入 funding、OI、爆仓、盘口等字段 |
| T10 | 自动化测试 | 待开始 | P1 | 补 pytest、前端 smoke test 和浏览器验收 |
| T11 | 监控与报告 | 待开始 | P2 | 补齐报告中心、监控告警和复盘摘要 |
| T12 | 文档维护 | 持续进行 | P0 | 保持 README、ARCHITECTURE、CONTEXT 与实现一致 |

## 近期执行顺序

### 第 1 阶段：Next.js 前端启动

目标：停止继续扩展 Streamlit UI，把产品化 UI 工作迁入 `frontend/`。

任务：
- 初始化 `frontend/`：Next.js App Router + React + TypeScript + Tailwind CSS。
- 建立首页、10 个页面路由、全局 shell、导航、基础 design tokens。
- 引入静态 seed 数据，先不接真实 API。
- Browser Use 验证 `http://127.0.0.1:3000` 首屏可加载、无控制台错误。

验收：
- `npm run dev` 可启动。
- 首页首屏是 Agent 挖因子工作台，不是营销页。
- 桌面宽视口布局优先向基准图收敛。

### 第 2 阶段：图片与图标资产

目标：解决当前 Streamlit 与基准图在图片、图标、画面风格上的差距。

任务：
- 用 imagegen 生成独立图片资产，而不是直接裁切整张基准图。
- 资产建议保存到：

```text
frontend/public/assets/mascot/
frontend/public/assets/stickers/
frontend/public/assets/illustrations/
frontend/public/assets/backgrounds/
```

首批资产：
- Agent 小助手：待机、生成中、成功、阻塞、告警、监控中。
- 贴纸：星星、云朵、便签、徽章、铃铛、盾牌。
- 功能插画：数据库、公式 fx、实验烧杯、折线图、报告文件、组合盒子。
- 空状态图：无任务、无数据、等待审核、任务阻塞。

验收：
- 资产尺寸和背景适合网页组件复用。
- Next.js 页面用 `<Image />` 或静态资源路径插入。
- 页面主体仍用 HTML/CSS/组件实现，不把整张设计图当背景。

### 第 3 阶段：核心工作台还原

目标：优先还原基准图中心的 `Agent 挖因子` 工作台。

任务：
- 三栏结构：左侧页面缩略图/导航，中间 Agent 工作台，右侧因子库/数据地图/图标规范区。
- 状态芯片：等待输入、生成中、待审核、执行中、已入库、监控中、阻塞。
- 8 步流程：提出目标、Agent 拆解、拉取数据、生成候选、批量回测、人工审核、入库/组合、监控迭代。
- 候选因子卡片、任务拆解卡片、数据验证卡片、因子库快照。

验收：
- 桌面宽视口接近基准图横向布局。
- 移动端可读，不发生文字遮挡和按钮溢出。

### 第 4 阶段：Python API 与真实数据

目标：让 Next.js 前端读取真实后端状态。

任务：
- 增加 Python API 层，建议 FastAPI。
- 只读接口优先：
  - `GET /api/overview`
  - `GET /api/agent/tasks`
  - `GET /api/agent/experiments`
  - `GET /api/factors/evaluations`
  - `GET /api/factors/decisions`
  - `GET /api/data/coverage`
- 前端封装 `frontend/src/lib/api.ts` 和类型 `frontend/src/lib/types.ts`。

验收：
- 前端能展示 `agent_factor_tasks`、`agent_factor_experiments`、`factor_evaluation`、`factor_decision`。
- 表缺失或数据为空时有清晰空状态。

### 第 5 阶段：受控操作闭环

目标：把前端从展示页升级为工作台。

任务：
- 创建候选任务。
- 人工审核通过或拒绝。
- 执行 approved 任务。
- 显示 skipped、blocked、failed、executed 的原因和日志摘要。

安全边界：
- 前端不能执行任意 Python。
- 自由文本公式不能直接执行，必须映射到 `formula_key + formula_params`。
- 所有执行入口必须复用后端 approved-only 和公式白名单。

验收：
- `draft/rejected/blocked/executed/failed` 不会误执行。
- 缺字段任务进入 `blocked`。
- 执行记录能在数据库中回查。

## 推荐 Sub-Agent 分片

| 分片 | 写入范围 | 交付物 |
|---|---|---|
| A. Next.js 骨架 | `frontend/package.json`、`frontend/src/app/`、基础配置 | 可启动前端工程 |
| B. 视觉系统 | `frontend/src/styles/`、`frontend/src/components/shell/` | design tokens、布局、导航 |
| C. Agent 工作台 | `frontend/src/components/agent-workbench/` | 目标输入、任务拆解、候选因子、审核状态 |
| D. 数据展示 | `frontend/src/components/charts/`、`frontend/src/components/factor-library/` | 图表、表格、因子卡片 |
| E. 资产生成 | `frontend/public/assets/` | mascot、贴纸、插画、空状态图 |
| F. API 层 | Python API 目录、`frontend/src/lib/` | 只读接口与前端类型 |
| G. 测试验收 | `tests/`、前端 smoke 脚本、Browser Use 截图记录 | 自动化和浏览器验收 |

## 当前阻塞

- Next.js 前端尚未初始化。
- Browser Use 当前打开的是 Streamlit 原型 `http://127.0.0.1:8501`，不是新技术栈页面。
- funding、OI、爆仓、盘口等字段尚未接入，相关 Agent 任务会继续 `blocked`。
- 自动化测试尚未建立，目前主要依赖脚本级验收。

## 下一次启动建议

1. 按 `FRONTEND_MIGRATION_PLAN.md` 初始化 `frontend/`。
2. 优先实现静态 seed 版 Agent 挖因子首页。
3. 用 imagegen 生成第一批网页资产。
4. 启动 `http://127.0.0.1:3000`，用 Browser Use 对照 `ui/agent_factor_ui_overview.png` 验收。
5. 再接 Python API 和真实 DuckDB 数据。
