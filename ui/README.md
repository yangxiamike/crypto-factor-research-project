# UI 最小可用版（Streamlit）

## 设计基准
Agent 挖因子系统的后续 UI 设计以 `ui/agent_factor_ui_overview.png` 为视觉基准，并由根目录 `UI_DESIGN_GUIDE.md` 维护页面体系、用户流程、图标和字体规范。

当前 `ui/app.py` 仍是最小可用 Streamlit 版本；后续重构前端时应向设计基准收敛，而不是延续旧版深色量化平台风格。

## 功能
- 输入 DuckDB 路径并直连读取（无后端服务）。
- 选择 `symbol`（基于 `market_bars`，若有 `asset_metadata` 会显示可读 symbol）。
- 选择时间范围。
- 展示收盘价折线（K 线替代）。
- 展示 `factor_evaluation` 最新一批结果（若无时间列则退化为前 200 行）。
- 对常见问题给出清晰错误提示：
  - 数据库文件不存在
  - 数据库为空
  - `market_bars` 表不存在或为空
  - 时间范围非法
  - `factor_evaluation` 表不存在/为空

## 依赖
建议在项目环境中安装：

```powershell
& "C:\Users\hp\anaconda3\envs\mt5\python.exe" -m pip install streamlit duckdb pandas
```

当前受限环境可使用项目本地依赖目录 `.tmp\pydeps`。启动脚本会自动把该目录加入 Python 路径。

## 启动
在项目根目录执行：

```powershell
& "C:\Users\hp\anaconda3\python.exe" scripts/start_ui.py
```

如果需要启动后保持独立窗口运行：

```powershell
scripts\start_ui.cmd
```

启动后在页面中填写 DuckDB 路径，例如：
- `./data/factor_research.duckdb`
- `C:/path/to/your.duckdb`

## 期望表
- 必需：`market_bars`
- 可选：`asset_metadata`、`factor_evaluation`

如果 `factor_evaluation` 缺少时间列（如 `evaluation_time`/`event_time` 等），页面会提示并退化展示筛选后的前 200 行。
