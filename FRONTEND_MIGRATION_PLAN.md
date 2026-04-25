# FRONTEND_MIGRATION_PLAN

## 目标

将当前 Streamlit 最小可用 UI 升级为可产品化的前端工程，用来承载 `ui/agent_factor_ui_overview.png` 中的 Agent 挖因子系统总览、10 个页面、8 步用户流程和精细视觉风格。

## 新技术栈

- 前端框架：Next.js App Router
- UI 运行时：React + TypeScript
- 样式：Tailwind CSS + CSS Modules/全局 design tokens
- 组件：优先自建业务组件，必要时引入 shadcn/ui 基础组件
- 图标：lucide-react + 项目自定义卡通贴纸/插画资产
- 图表：Recharts 或 ECharts，按数据密度选择
- 后端 API：Python FastAPI 或现有脚本封装出的 HTTP API
- 存储：继续使用 DuckDB + Parquet

## 当前 Streamlit 定位

`ui/app.py` 保留为研究原型和数据联调入口，不再作为最终 UI 技术路线。

适用场景：
- 快速检查 DuckDB 数据是否可读。
- 验证后端表结构和评估结果。
- 在 Next.js 前端未完成前做内部 smoke test。

不再承担：
- 精细还原 UI 基准图。
- 复杂响应式布局。
- 复杂交互状态、动画、组件复用和产品化体验。

## 目标目录建议

```text
frontend/
  package.json
  next.config.ts
  tsconfig.json
  src/
    app/
      layout.tsx
      page.tsx
      agent/
        page.tsx
      lab/
        page.tsx
      backtest/
        page.tsx
      factors/
        page.tsx
      data-map/
        page.tsx
      portfolio/
        page.tsx
      reports/
        page.tsx
      monitor/
        page.tsx
      settings/
        page.tsx
    components/
      shell/
      cards/
      charts/
      agent-workbench/
      factor-library/
      data-map/
    lib/
      api.ts
      types.ts
      format.ts
    styles/
      tokens.css
```

Python 后端继续保留在 `src/factor_research` 和 `scripts` 下。Next.js 不直接重写研究计算逻辑，只通过 API 读取任务、实验、评估、决策和监控数据。

## 数据与 API 边界

第一阶段 API 只读为主：
- `GET /api/overview`：总览驾驶舱指标。
- `GET /api/agent/tasks`：Agent 任务列表与状态。
- `GET /api/agent/experiments`：实验摘要。
- `GET /api/factors/evaluations`：因子评估结果。
- `GET /api/factors/decisions`：因子判定结果。
- `GET /api/data/coverage`：数据地图覆盖状态。

第二阶段再开放受控写操作：
- `POST /api/agent/tasks`：创建候选任务。
- `POST /api/agent/tasks/{id}/approve`：人工审核通过。
- `POST /api/agent/tasks/{id}/reject`：人工拒绝。
- `POST /api/agent/tasks/run-approved`：执行已审核任务。

所有写操作都必须保留人工确认，不让前端直接触发任意 Python 代码。

## 分阶段更新方案

### 阶段 0：文档和口径切换

目标：明确新技术栈和迁移边界。

任务：
- 更新 README、ARCHITECTURE、UI_DESIGN_GUIDE 和 CONTEXT。
- 新增本迁移方案文档。
- 明确 Streamlit 是临时原型，Next.js 是目标前端。

验收：
- 项目文档中技术栈口径一致。
- 后续 UI 任务都以 Next.js 方案拆分。

### 阶段 1：Next.js 前端骨架

目标：建立可启动的前端工程。

任务：
- 在 `frontend/` 初始化 Next.js App Router + TypeScript + Tailwind。
- 建立全局 layout、导航、页面路由和基础 design tokens。
- 接入静态 seed 数据，先还原基准图的整体布局比例。

验收：
- `npm run dev` 可启动。
- 首页首屏直接进入 Agent 挖因子工作台，不做营销页。
- Browser Use 验证桌面和移动视口无控制台错误。

### 阶段 2：视觉基准还原

目标：优先解决当前 Streamlit 无法还原的视觉问题。

任务：
- 还原浅色纸张背景、圆润描边、状态芯片、10 页面缩略图、8 步流程。
- 建立卡通贴纸和图标资产规范。
- 完成核心 `Agent 挖因子` 工作台三栏布局。

验收：
- 桌面宽视口下接近 `ui/agent_factor_ui_overview.png` 的横向结构。
- 移动端不重叠、不溢出、不出现不可读文本。

### 阶段 3：只读数据接入

目标：用真实 DuckDB 结果替换 seed 数据。

任务：
- 增加 Python API 层，读取 DuckDB。
- 前端接入任务、实验、评估、判定和数据覆盖。
- 图表和表格使用真实字段。

验收：
- UI 能展示 `agent_factor_tasks`、`agent_factor_experiments`、`factor_evaluation`、`factor_decision`。
- 数据为空或表缺失时有清晰空状态。

### 阶段 4：受控操作闭环

目标：把 UI 从展示升级为工作台。

任务：
- 支持创建候选任务、审核、拒绝、执行 approved 任务。
- 写操作走 API 白名单，不执行任意代码。
- 加入操作结果、失败原因、blocked 字段缺失提示。

验收：
- 非 approved 任务不会执行。
- 缺字段任务进入 blocked。
- 操作记录可回查。

### 阶段 5：监控和报告

目标：补齐产品化后续流程。

任务：
- 因子库、组合工作台、监控告警、报告中心接入真实数据。
- 支持研究报告导出和 Agent 复盘摘要。
- 增加可视化回归验收截图。

验收：
- 8 步用户流程能从 UI 走通。
- Browser Use 验收核心页面和关键交互。

## 关键约束

- 不在 Next.js 中重写因子计算核心；研究逻辑仍在 Python。
- 前端写操作必须通过受控 API，不允许直接拼接执行脚本。
- 保留 point-in-time、approved-only、公式白名单和 blocked 状态语义。
- 视觉开发必须继续以 `ui/agent_factor_ui_overview.png` 为唯一基准图。
- Next.js 数据客户端和服务端 SDK 不在模块顶层初始化，避免构建阶段环境变量或资源缺失导致失败。
