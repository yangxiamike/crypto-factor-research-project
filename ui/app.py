from __future__ import annotations

from html import escape
from pathlib import Path
import site
from typing import Any

site.addsitedir(site.getusersitepackages())

import duckdb
import pandas as pd
import streamlit as st

from agent_ui_data import get_agent_workspace_seed
from agent_ui_style import (
    badge_html,
    badge_row_html,
    card_html,
    inject_agent_ui_style,
    status_badge_html,
)


PAGES = [
    "总览驾驶舱",
    "Agent 挖因子",
    "因子实验室",
    "回测与归因",
    "因子库",
    "数据地图",
    "组合工作台",
    "报告中心",
    "监控与告警",
    "设置",
]

PAGE_HINTS = {
    "总览驾驶舱": "任务状态、活跃 Agent、数据接入和监控风险的总览。",
    "Agent 挖因子": "从研究目标到任务拆解、候选因子、人工审核的核心工作台。",
    "因子实验室": "公式白名单映射、字段覆盖、风险检查和候选质量对比。",
    "回测与归因": "展示 IC、收益、回撤、换手和归因状态。",
    "因子库": "管理已入库因子、标签、谱系、版本和复用状态。",
    "数据地图": "检查行情、衍生品、盘口、链上与情绪数据的接入状态。",
    "组合工作台": "选择因子、配置权重、设置约束和 paper/live 状态。",
    "报告中心": "沉淀研究备忘录、审核记录和复盘报告。",
    "监控与告警": "跟踪因子衰减、漂移、缺数和重跑建议。",
    "设置": "配置模型、数据权限、执行开关和团队角色。",
}


st.set_page_config(page_title="Agent 挖因子系统", layout="wide")
inject_agent_ui_style(st)


def _list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
        """
    ).fetchall()
    return [row[0] for row in rows]


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return table_name in _list_tables(con)


def _get_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {row[1] for row in rows}


def _pick_first(columns: set[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


def _safe_query(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    params: tuple | None = None,
) -> pd.DataFrame:
    if params is None:
        return con.execute(sql).df()
    return con.execute(sql, params).df()


def _resolve_market_bar_columns(con: duckdb.DuckDBPyConnection) -> tuple[str, str, str]:
    cols = _get_columns(con, "market_bars")
    asset_col = _pick_first(cols, ["asset_id", "symbol", "exchange_symbol"])
    time_col = _pick_first(cols, ["event_time", "open_time", "close_time", "bar_time", "timestamp", "time"])
    close_col = _pick_first(cols, ["close", "close_price", "price", "last_price"])
    if asset_col is None or time_col is None or close_col is None:
        raise RuntimeError("market_bars 缺少必要字段，至少需要资产列、时间列、收盘价列。")
    return asset_col, time_col, close_col


def _load_symbol_options(con: duckdb.DuckDBPyConnection, asset_col: str) -> pd.DataFrame:
    has_bars = _table_exists(con, "market_bars")
    has_meta = _table_exists(con, "asset_metadata")

    if not has_bars:
        return pd.DataFrame(columns=["asset_key", "display_symbol"])

    if has_meta:
        meta_cols = _get_columns(con, "asset_metadata")
        meta_asset_col = _pick_first(meta_cols, [asset_col, "asset_id", "symbol", "exchange_symbol"])
        meta_symbol_col = _pick_first(meta_cols, ["symbol", "asset_id", "exchange_symbol"])
        if meta_asset_col is not None and meta_symbol_col is not None:
            sql = f"""
            SELECT DISTINCT
                m.{asset_col} AS asset_key,
                COALESCE(a.{meta_symbol_col}, m.{asset_col}) AS display_symbol
            FROM market_bars m
            LEFT JOIN asset_metadata a ON m.{asset_col} = a.{meta_asset_col}
            ORDER BY 2, 1
            """
            return _safe_query(con, sql)

    sql = f"""
    SELECT DISTINCT
        {asset_col} AS asset_key,
        {asset_col} AS display_symbol
    FROM market_bars
    ORDER BY 1
    """
    return _safe_query(con, sql)


def _load_time_bounds(
    con: duckdb.DuckDBPyConnection,
    asset_col: str,
    time_col: str,
    asset_key: str,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    sql = f"""
    SELECT
        MIN(CAST({time_col} AS TIMESTAMP)) AS min_ts,
        MAX(CAST({time_col} AS TIMESTAMP)) AS max_ts
    FROM market_bars
    WHERE {asset_col} = ?
    """
    df = _safe_query(con, sql, (asset_key,))
    if df.empty:
        return None, None
    return df.iloc[0]["min_ts"], df.iloc[0]["max_ts"]


def _load_price_series(
    con: duckdb.DuckDBPyConnection,
    asset_col: str,
    time_col: str,
    close_col: str,
    asset_key: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    sql = f"""
    SELECT
        CAST({time_col} AS TIMESTAMP) AS event_time,
        {close_col} AS close
    FROM market_bars
    WHERE {asset_col} = ?
      AND CAST({time_col} AS TIMESTAMP) BETWEEN ? AND ?
    ORDER BY event_time
    """
    return _safe_query(con, sql, (asset_key, start_ts, end_ts))


def _load_latest_evaluation(
    con: duckdb.DuckDBPyConnection,
    asset_key: str | None,
) -> tuple[pd.DataFrame, str | None]:
    if not _table_exists(con, "factor_evaluation"):
        return pd.DataFrame(), "当前数据库尚未落库 factor_evaluation，评估结果区展示为空状态。"

    cols = _get_columns(con, "factor_evaluation")
    time_candidates = [
        "evaluation_time",
        "event_time",
        "factor_time",
        "snapshot_time",
        "label_end_time",
        "ingested_time",
        "created_at",
        "updated_at",
    ]
    time_col = next((c for c in time_candidates if c in cols), None)

    symbol_filter_col = None
    if asset_key is not None:
        if "asset_id" in cols:
            symbol_filter_col = "asset_id"
        elif "symbol" in cols:
            symbol_filter_col = "symbol"

    if time_col is not None:
        if symbol_filter_col is not None:
            sql = f"""
            SELECT *
            FROM factor_evaluation
            WHERE {time_col} = (
                SELECT MAX({time_col})
                FROM factor_evaluation
                WHERE {symbol_filter_col} = ?
            )
              AND {symbol_filter_col} = ?
            """
            df = _safe_query(con, sql, (asset_key, asset_key))
        else:
            sql = f"""
            SELECT *
            FROM factor_evaluation
            WHERE {time_col} = (SELECT MAX({time_col}) FROM factor_evaluation)
            """
            df = _safe_query(con, sql)

        if df.empty:
            return pd.DataFrame(), "factor_evaluation 表存在，但最新批次无记录。"
        return df, None

    if symbol_filter_col is not None:
        sql = f"SELECT * FROM factor_evaluation WHERE {symbol_filter_col} = ? LIMIT 200"
        df = _safe_query(con, sql, (asset_key,))
    else:
        sql = "SELECT * FROM factor_evaluation LIMIT 200"
        df = _safe_query(con, sql)

    if df.empty:
        return pd.DataFrame(), "factor_evaluation 表为空。"
    return df, "factor_evaluation 缺少时间列，当前展示筛选后的前 200 行。"


@st.cache_data(show_spinner=False)
def _load_db_snapshot(db_path_text: str) -> dict[str, Any]:
    db_path = Path(db_path_text).expanduser()
    snapshot: dict[str, Any] = {
        "ok": False,
        "db_path": str(db_path),
        "tables": [],
        "table_counts": {},
        "error": None,
        "symbols": pd.DataFrame(),
        "asset_col": None,
        "time_col": None,
        "close_col": None,
    }
    if not db_path_text.strip():
        snapshot["error"] = "请先输入 DuckDB 文件路径。"
        return snapshot
    if not db_path.exists():
        snapshot["error"] = f"数据库文件不存在: {db_path}"
        return snapshot

    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception as exc:
        snapshot["error"] = f"连接 DuckDB 失败: {exc}"
        return snapshot

    try:
        tables = _list_tables(con)
        snapshot["tables"] = tables
        snapshot["table_counts"] = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        if "market_bars" in tables:
            asset_col, time_col, close_col = _resolve_market_bar_columns(con)
            snapshot["asset_col"] = asset_col
            snapshot["time_col"] = time_col
            snapshot["close_col"] = close_col
            snapshot["symbols"] = _load_symbol_options(con, asset_col=asset_col)
        snapshot["ok"] = True
    except Exception as exc:
        snapshot["error"] = f"读取数据库概览失败: {exc}"
    finally:
        con.close()
    return snapshot


def _format_percent(value: float) -> str:
    return f"{value:.1%}"


def _mini_bar_html(value: int, color: str = "#58B37D") -> str:
    safe_value = max(0, min(value, 100))
    return (
        "<div style='height:10px;border-radius:999px;background:#EEF2F7;overflow:hidden;'>"
        f"<div style='width:{safe_value}%;height:100%;border-radius:999px;background:{color};'></div>"
        "</div>"
    )


def _render_system_banner(seed: dict[str, Any], page: str) -> None:
    status_chips = []
    for chip in seed.get("top_status_chips", []):
        status_chips.append(
            "<div class='agent-top-chip'>"
            f"<span>{escape(str(chip['icon']))}</span>"
            f"<div><b>{escape(str(chip['value']))}</b><small>{escape(str(chip['label']))}</small></div>"
            f"{status_badge_html(str(chip['status']), _status_label(seed, str(chip['status'])))}"
            "</div>"
        )
    st.markdown(
        f"""
        <section class="agent-hero-shell">
          <div class="agent-mascot-card">
            <div class="agent-mascot-face">AI</div>
            <div class="agent-sparkle">research buddy</div>
          </div>
          <div class="agent-hero-main">
            <div class="agent-kicker">Crypto Factor Research</div>
            <div class="agent-hero-title">Agent 挖因子系统 UI 总览</div>
            <div class="agent-hero-flow">从研究目标 -> Agent 拆解 -> 数据验证 -> 因子回测 -> 人工审核 -> 入库监控</div>
          </div>
          <div class="agent-status-board">
            <div class="agent-status-title">状态芯片（系统全局统一）</div>
            {badge_row_html([
                status_badge_html("waiting", "等待输入"),
                status_badge_html("generating", "生成中"),
                status_badge_html("review", "待审核"),
                status_badge_html("running", "执行中"),
                status_badge_html("stored", "已入库"),
                status_badge_html("monitoring", "监控中"),
                status_badge_html("error", "阻塞"),
            ])}
          </div>
          <div class="agent-note-card">
            <div>后续系统</div>
            <strong>方案与本图对齐</strong>
            <span>当前页面：{escape(page)}</span>
          </div>
        </section>
        <section class="agent-overview-ribbon">{"".join(status_chips)}</section>
        """,
        unsafe_allow_html=True,
    )


def _status_label(seed: dict[str, Any], status: str) -> str:
    item = seed["status_catalog"].get(status)
    if not item:
        return status
    return str(item["label"])


def _render_header(page: str) -> None:
    st.markdown(
        f"""
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin:14px 0 8px;">
          <div>
            <div style="font-size:0.88rem;color:#5F6F95;font-weight:800;">当前工作区</div>
            <h1 style="margin:0;font-size:1.8rem;line-height:1.15;">{escape(page)}</h1>
            <div style="color:#64708F;margin-top:6px;">{escape(PAGE_HINTS[page])}</div>
          </div>
          <div style="text-align:right;min-width:230px;">
            {badge_row_html([
                status_badge_html("generating", "Agent 生成中"),
                status_badge_html("review", "待审核"),
                status_badge_html("stored", "已入库"),
            ])}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_db_status(snapshot: dict[str, Any]) -> None:
    if snapshot["error"]:
        st.warning(snapshot["error"])
        return
    counts = snapshot["table_counts"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DuckDB 表", len(snapshot["tables"]))
    c2.metric("行情行数", counts.get("market_bars", 0))
    c3.metric("资产元数据", counts.get("asset_metadata", 0))
    c4.metric("评估结果", counts.get("factor_evaluation", 0))
    st.caption("已发现表: " + (", ".join(snapshot["tables"]) if snapshot["tables"] else "无"))


def _render_workflow(seed: dict[str, Any]) -> None:
    step_items = []
    for step in seed["workflow_steps"]:
        status = step["current_status"]
        step_items.append(
            f"""
            <div class="agent-flow-step">
              <div class="agent-flow-number">{step["step_no"]}</div>
              <div class="agent-flow-name">{escape(step["step_name"])}</div>
              <div class="agent-flow-sub">{escape(step["output"])}</div>
              {status_badge_html(status, _status_label(seed, status))}
            </div>
            """
        )
    st.markdown(
        "<div class='agent-section-title'>完整用户流程（8 步）</div>"
        "<div class='agent-flow-strip'>"
        + "<div class='agent-flow-line'></div>".join(step_items)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_page_map(seed: dict[str, Any]) -> None:
    page_rows = []
    accent = ["#4CA66A", "#2F8BCB", "#7768D8", "#E56E3F", "#349B85", "#C88B2C", "#8A6AC8", "#CF5E84", "#D65F48", "#2E84C8"]
    for index, page_name in enumerate(PAGES, start=1):
        page_rows.append(
            f"""
            <div class="agent-page-tile" style="--tile-accent:{accent[index - 1]};">
              <div class="agent-page-index">{index}</div>
              <div>
                <strong>{escape(page_name)}</strong>
                <span>{escape(PAGE_HINTS[page_name])}</span>
              </div>
            </div>
            """
        )
    st.markdown(
        "<div class='agent-section-title'>10 个页面缩略图</div>"
        "<div class='agent-page-map'>"
        + "".join(page_rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_icon_and_type_system(seed: dict[str, Any]) -> None:
    icon_items = seed.get("icon_library", [])[:12]
    font_spec = seed.get("font_spec", {})
    icons = "".join(
        f"<div class='agent-icon-chip'><div>{escape(str(item['emoji']))}</div><span>{escape(str(item['label']))}</span></div>"
        for item in icon_items
    )
    st.markdown(
        f"""
        <div class="agent-side-spec">
          <div class="agent-section-title">交互图标</div>
          <div class="agent-icon-grid">{icons}</div>
          <div class="agent-type-card">
            <div><b>Aa</b><span>标题：{escape(str(font_spec.get("title_font", "Noto Sans SC Heavy")))}</span></div>
            <div><b>Aa</b><span>正文：{escape(str(font_spec.get("body_font", "Noto Sans SC Regular")))}</span></div>
            <div><b>123</b><span>数字：{escape(str(font_spec.get("number_font", "JetBrains Mono / Consolas")))}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_agent_workspace(seed: dict[str, Any]) -> None:
    objective = seed["research_objective"]
    pool_stats = seed.get("candidate_pool_stats", {})
    total_candidates = int(pool_stats.get("total_candidates", 36))
    coverage_ratio = float(pool_stats.get("coverage_ratio", 0.83))
    progress_text = seed.get("top_status_chips", [{}])[0].get("value", "8/12 任务")
    st.markdown("<div class='agent-workbench-title'>Agent 挖因子</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="agent-command-bar">
          <div class="agent-helper-card">
            <div class="agent-helper-avatar">AI</div>
            <div>
              <b>生成中</b>
              <span>已完成 8/12 个任务，正在生成候选因子</span>
            </div>
          </div>
          <div class="agent-progress-pill">
            <span>进度</span><b>{int(coverage_ratio * 100)}%</b>{_mini_bar_html(int(coverage_ratio * 100))}
          </div>
          <div class="agent-task-pill"><span>任务</span><b>{escape(str(progress_text))}</b></div>
          <div class="agent-task-pill"><span>候选因子</span><b>{total_candidates}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, mid, right = st.columns([0.82, 1.24, 1])

    with left:
        nav_items = ["总览", "挖因子", "实验室", "回测", "因子库", "数据", "组合", "报告", "监控", "设置"]
        st.markdown(
            "<div class='agent-mini-nav'>"
            + "".join(
                f"<div class='{'active ' if item == '挖因子' else ''}agent-mini-nav-item'><span>{escape(item)}</span></div>"
                for item in nav_items
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        user_goal = st.text_area(
            "研究目标",
            value=objective["title"],
            height=118,
            help="这里模拟研究员提交目标，按钮会驱动本地 UI 状态变化。",
        )
        c1, c2, c3 = st.columns([1, 1, 1])
        if c1.button("生成任务", use_container_width=True):
            st.session_state["agent_progress"] = min(st.session_state.get("agent_progress", 45) + 20, 100)
            st.session_state["last_action"] = "Agent 已重新拆解目标。"
        if c2.button("执行已通过", use_container_width=True):
            st.session_state["agent_progress"] = 78
            st.session_state["last_action"] = "已将审核通过任务放入回测队列。"
        if c3.button("重跑检查", use_container_width=True):
            st.session_state["agent_progress"] = 62
            st.session_state["last_action"] = "已触发字段可得性与 PIT 风险检查。"

        progress = st.session_state.get("agent_progress", 65)
        st.progress(progress, text=f"任务进度 {progress}%")
        st.info(st.session_state.get("last_action", "已完成 8/12 个任务，正在生成候选因子。"))
        st.markdown(
            card_html(
                f"""
                <div><b>目标范围</b>：{escape(", ".join(objective["universe"]))}</div>
                <div><b>频率</b>：{escape(objective["frequency"])}　<b>预测周期</b>：{escape(", ".join(objective["horizons"]))}</div>
                <div><b>检测口径</b>：{escape(objective["neutralization_profile"])}</div>
                <div><b>说明</b>：{escape(objective["note"])}</div>
                """,
                title="研究目标卡",
                right_html=badge_html(objective["risk_preference"], tone="warning"),
            ),
            unsafe_allow_html=True,
        )

    with mid:
        tabs = st.tabs(["任务拆解", "候选因子", "Agent 对话"])
        with tabs[0]:
            st.markdown(
                "<div class='agent-phase-row'>"
                "<div>理解目标</div><div>拆解维度</div><div>数据需求</div><div>构建逻辑</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            for task in seed["task_breakdown"]:
                st.markdown(
                    card_html(
                        f"""
                        <div>{escape(task["hypothesis"])}</div>
                        <div style='margin-top:8px'>{badge_row_html([
                            badge_html(task["priority"], "primary"),
                            badge_html(task["formula_key"], "neutral"),
                            status_badge_html(task["status"], _status_label(seed, task["status"])),
                        ])}</div>
                        """,
                        title=task["factor_name"],
                        subtitle=f'{task["task_id"]} / {task["owner_agent"]}',
                        compact=True,
                    ),
                    unsafe_allow_html=True,
                )
        with tabs[1]:
            _render_candidate_cards(seed)
        with tabs[2]:
            st.chat_message("assistant").write("我已把目标拆成价格成交量、资金费率拥挤、盘口失衡、链上活跃四类候选。")
            st.chat_message("user").write(user_goal)
            st.chat_message("assistant").write("当前只有 OHLCV 可以直接执行；funding、OI、盘口、链上字段需要先补数据或进入 blocked。")

    with right:
        st.markdown("<div class='agent-section-title'>数据与验证</div>", unsafe_allow_html=True)
        coverage = seed.get("data_map_coverage", {})
        validated_ratio = int(float(coverage.get("validated_ratio", coverage_ratio)) * 100)
        st.markdown(
            card_html(
                f"""
                <div class="agent-validation-grid">
                  <div>行情数据 {status_badge_html("success", "可用")}</div>
                  <div>财务数据 {status_badge_html("success", "可用")}</div>
                  <div>资金费率 {status_badge_html("running", "执行中")}</div>
                  <div>事件数据 {status_badge_html("blocked", "等待")}</div>
                </div>
                <div style="margin-top:14px;">
                  <div style="display:flex;justify-content:space-between;color:#697492;font-weight:700;"><span>数据覆盖</span><span>{validated_ratio}%</span></div>
                  {_mini_bar_html(validated_ratio)}
                </div>
                <div class="agent-data-foot">交易所 {coverage.get("exchange_count", 2)} / 标的 {coverage.get("symbol_count", 4)} / 字段 {coverage.get("core_field_count", 14)}</div>
                """,
                title="数据与验证",
                subtitle="多源字段校验",
            ),
            unsafe_allow_html=True,
        )
        st.markdown("<div class='agent-section-title'>因子库快照</div>", unsafe_allow_html=True)
        factor_rows = []
        factor_table = seed.get("factor_library_table", {})
        for item in factor_table.get("rows", seed["factor_library"]):
            factor_rows.append(
                f"<tr><td>{escape(item['factor_name'])}</td><td>{status_badge_html(item['library_status'], _status_label(seed, item['library_status']))}</td><td>{item['quality_score']}%</td></tr>"
            )
        st.markdown(
            "<table class='agent-mini-table'><thead><tr><th>因子名</th><th>状态</th><th>质量</th></tr></thead><tbody>"
            + "".join(factor_rows)
            + "</tbody></table>",
            unsafe_allow_html=True,
        )


def _render_candidate_cards(seed: dict[str, Any]) -> None:
    for candidate in seed["candidate_factors"]:
        status_key = st.session_state.get(f"candidate_status_{candidate['candidate_id']}", candidate["status"])
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                card_html(
                    f"""
                    <div style='display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;'>
                      <div><b>IC 均值</b><br>{candidate["ic_mean"]:.3f}</div>
                      <div><b>多空 Sharpe</b><br>{candidate["long_short_sharpe"]:.2f}</div>
                      <div><b>最大回撤</b><br>{candidate["max_drawdown"]:.1%}</div>
                    </div>
                    <div style='margin-top:8px;color:#687494;'>验收差距：{escape(candidate["acceptance_gap"])}</div>
                    """,
                    title=candidate["factor_name"],
                    subtitle=f'{candidate["candidate_id"]} / {candidate["formula_key"]}',
                    right_html=status_badge_html(status_key, _status_label(seed, status_key)),
                    compact=True,
                ),
                unsafe_allow_html=True,
            )
        with col2:
            st.write("")
            if st.button("通过", key=f"approve_{candidate['candidate_id']}", use_container_width=True):
                st.session_state[f"candidate_status_{candidate['candidate_id']}"] = "approved"
                st.session_state["last_action"] = f"{candidate['factor_name']} 已标记为审核通过。"
            if st.button("拒绝", key=f"reject_{candidate['candidate_id']}", use_container_width=True):
                st.session_state[f"candidate_status_{candidate['candidate_id']}"] = "rejected"
                st.session_state["last_action"] = f"{candidate['factor_name']} 已标记为审核拒绝。"


def _render_overview(seed: dict[str, Any], snapshot: dict[str, Any]) -> None:
    cols = st.columns(4)
    for col, metric in zip(cols, seed["overview_metrics"]):
        col.metric(metric["metric"], metric["value"], metric["delta"])
    _render_workflow(seed)
    map_col, spec_col = st.columns([1.35, 1])
    with map_col:
        _render_page_map(seed)
    with spec_col:
        _render_icon_and_type_system(seed)
    st.subheader("活跃 Agent")
    agent_cols = st.columns(3)
    for col, agent in zip(agent_cols, seed["active_agents"]):
        col.markdown(
            card_html(
                f"<div>队列：<b>{agent['queue_size']}</b> 个任务</div>",
                title=agent["role"],
                subtitle=agent["agent_id"],
                right_html=status_badge_html(agent["status"], _status_label(seed, agent["status"])),
            ),
            unsafe_allow_html=True,
        )
    st.subheader("真实数据接入")
    _render_db_status(snapshot)


def _render_lab(seed: dict[str, Any]) -> None:
    st.subheader("公式白名单与字段检查")
    for task in seed["task_breakdown"]:
        with st.expander(f"{task['factor_name']} / {task['task_id']}", expanded=task["status"] in {"approved", "pending_review"}):
            c1, c2 = st.columns([1.1, 1])
            c1.code(task["formula_draft"], language="text")
            c1.write("白名单公式：", task["formula_key"])
            c2.write("必需字段：", ", ".join(task["required_fields"]))
            c2.write("参数：", task["formula_params"])
            c2.write("风险检查：", ", ".join(task["risk_checks"]))
            st.markdown(status_badge_html(task["status"], _status_label(seed, task["status"])), unsafe_allow_html=True)


def _render_backtest(seed: dict[str, Any], snapshot: dict[str, Any], db_path_text: str) -> None:
    st.subheader("候选评估")
    st.dataframe(pd.DataFrame(seed["candidate_factors"]), use_container_width=True, hide_index=True)
    st.subheader("真实行情样本")
    _render_market_browser(snapshot, db_path_text)


def _render_market_browser(snapshot: dict[str, Any], db_path_text: str) -> None:
    if snapshot["error"]:
        st.warning(snapshot["error"])
        return
    if "market_bars" not in snapshot["tables"]:
        st.info("缺少 market_bars，暂无真实行情可展示。")
        return
    symbol_df = snapshot["symbols"]
    if symbol_df.empty:
        st.info("market_bars 表为空，暂无可选 symbol。")
        return

    symbol_map = {
        f"{row['display_symbol']} ({row['asset_key']})": row["asset_key"]
        for _, row in symbol_df.iterrows()
    }
    symbol_label = st.selectbox("Symbol", options=list(symbol_map.keys()))
    selected_asset_key = symbol_map[symbol_label]

    con = duckdb.connect(str(Path(db_path_text).expanduser()), read_only=True)
    try:
        min_ts, max_ts = _load_time_bounds(con, snapshot["asset_col"], snapshot["time_col"], selected_asset_key)
        if min_ts is None or max_ts is None or pd.isna(min_ts) or pd.isna(max_ts):
            st.error("该 symbol 没有可用时间范围。")
            return
        c1, c2 = st.columns(2)
        start_date = c1.date_input("开始日期", value=min_ts.date(), min_value=min_ts.date(), max_value=max_ts.date())
        end_date = c2.date_input("结束日期", value=max_ts.date(), min_value=min_ts.date(), max_value=max_ts.date())
        if start_date > end_date:
            st.error("时间范围错误：开始日期不能晚于结束日期。")
            return
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        price_df = _load_price_series(
            con,
            snapshot["asset_col"],
            snapshot["time_col"],
            snapshot["close_col"],
            selected_asset_key,
            start_ts,
            end_ts,
        )
    finally:
        con.close()

    if price_df.empty:
        st.info("所选时间范围内无行情数据。")
    else:
        price_df = price_df.set_index("event_time")
        st.line_chart(price_df[["close"]])
        st.dataframe(price_df.tail(20), use_container_width=True)


def _render_library(seed: dict[str, Any]) -> None:
    st.subheader("因子库")
    df = pd.DataFrame(seed["factor_library"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_data_map(seed: dict[str, Any], snapshot: dict[str, Any]) -> None:
    st.subheader("数据地图")
    for item in seed["data_map"]:
        st.markdown(
            card_html(
                f"""
                <div><b>字段</b>：{escape(", ".join(item["core_fields"]))}</div>
                <div><b>覆盖</b>：{escape(item["coverage"])}　<b>延迟</b>：{escape(item["latency_level"])}</div>
                <div style='margin-top:8px;color:#697492;'>{escape(item["note"])}</div>
                """,
                title=item["domain"],
                subtitle=f'{item["source"]} / freshness {item["freshness"]}',
                right_html=status_badge_html(item["status"], _status_label(seed, item["status"])),
            ),
            unsafe_allow_html=True,
        )
    st.subheader("当前 DuckDB")
    _render_db_status(snapshot)


def _render_portfolio(seed: dict[str, Any]) -> None:
    st.subheader("组合工作台")
    enabled = st.multiselect(
        "选择因子",
        [item["factor_name"] for item in seed["factor_library"]],
        default=[seed["factor_library"][0]["factor_name"]],
    )
    weight = st.slider("单因子最大权重", min_value=5, max_value=40, value=20, step=5)
    st.toggle("paper 运行", value=True)
    st.toggle("live 运行", value=False)
    st.markdown(
        card_html(
            f"<div>已选择 <b>{len(enabled)}</b> 个因子，单因子权重上限 <b>{weight}%</b>。live 开关保留人工确认。</div>",
            title="组合草案",
            right_html=status_badge_html("monitoring", "paper"),
        ),
        unsafe_allow_html=True,
    )


def _render_reports(seed: dict[str, Any]) -> None:
    st.subheader("报告中心")
    objective = seed["research_objective"]
    st.markdown(
        card_html(
            f"""
            <div><b>标题</b>：{escape(objective["title"])}</div>
            <div><b>结论</b>：OHLCV 相关因子可进入受控执行；funding/OI/盘口/链上类先进入数据补齐队列。</div>
            <div><b>下一步</b>：补 `factor_evaluation` 落库后打通最新评估展示。</div>
            """,
            title="研究备忘录草稿",
            subtitle="2026-04-25",
            right_html=badge_html("可导出", "primary"),
        ),
        unsafe_allow_html=True,
    )
    st.dataframe(pd.DataFrame(seed["candidate_factors"])[["factor_name", "acceptance_gap", "status"]], use_container_width=True, hide_index=True)


def _render_monitor(seed: dict[str, Any]) -> None:
    st.subheader("监控与告警")
    for alert in seed["monitor_alerts"]:
        tone = "danger" if alert["severity"] == "high" else "warning"
        st.markdown(
            card_html(
                f"""
                <div><b>{escape(alert["metric_name"])}</b>：{alert["current_value"]} / 阈值 {alert["threshold"]}</div>
                <div style='margin-top:8px;color:#697492;'>{escape(alert["suggestion"])}</div>
                """,
                title=f'{alert["alert_type"]} - {alert["factor_name"]}',
                subtitle=alert["trigger_time"],
                right_html=badge_row_html([
                    badge_html(alert["severity"], tone),
                    status_badge_html(alert["status"], _status_label(seed, alert["status"])),
                ]),
            ),
            unsafe_allow_html=True,
        )


def _render_settings(seed: dict[str, Any]) -> None:
    st.subheader("设置")
    c1, c2 = st.columns(2)
    c1.selectbox("主调度模型", ["GPT-5.5 / medium", "GPT-5.5 / high"], index=0)
    c2.selectbox("编码分片模型", ["GPT-5.3 / medium", "GPT-5.3 / high"], index=0)
    st.checkbox("只执行 approved 任务", value=True)
    st.checkbox("自由文本公式必须映射到 formula_key", value=True)
    st.checkbox("入库/组合/live 前保留人工确认", value=True)
    st.dataframe(pd.DataFrame(seed["active_agents"]), use_container_width=True, hide_index=True)


def _render_latest_evaluation(snapshot: dict[str, Any], db_path_text: str) -> None:
    st.subheader("最新一批因子评估结果")
    if snapshot["error"] or "market_bars" not in snapshot["tables"]:
        st.info("需要有效 DuckDB 和 market_bars 后才能尝试读取评估结果。")
        return
    asset_key = None
    if not snapshot["symbols"].empty:
        asset_key = str(snapshot["symbols"].iloc[0]["asset_key"])
    con = duckdb.connect(str(Path(db_path_text).expanduser()), read_only=True)
    try:
        eval_df, eval_msg = _load_latest_evaluation(con, asset_key)
    finally:
        con.close()
    if eval_msg:
        st.info(eval_msg)
    if eval_df.empty:
        st.warning("暂无可展示的因子评估结果。")
    else:
        st.dataframe(eval_df, use_container_width=True)


def main() -> None:
    seed = get_agent_workspace_seed()

    if "agent_progress" not in st.session_state:
        st.session_state["agent_progress"] = 65

    with st.sidebar:
        st.markdown("### Agent 挖因子")
        page = st.radio("页面", PAGES, index=1)
        st.divider()
        db_path_text = st.text_input("DuckDB 路径", value="./data/factor_research.duckdb")
        snapshot = _load_db_snapshot(db_path_text)
        if snapshot["error"]:
            st.caption(snapshot["error"])
        else:
            st.caption(f"已连接：{Path(db_path_text).name}")
            st.caption(f"表：{len(snapshot['tables'])} / 行情：{snapshot['table_counts'].get('market_bars', 0)}")
        st.divider()
        st.caption("视觉基准：ui/agent_factor_ui_overview.png")

    _render_system_banner(seed, page)
    _render_header(page)

    if page == "总览驾驶舱":
        _render_overview(seed, snapshot)
    elif page == "Agent 挖因子":
        _render_agent_workspace(seed)
        _render_latest_evaluation(snapshot, db_path_text)
    elif page == "因子实验室":
        _render_lab(seed)
    elif page == "回测与归因":
        _render_backtest(seed, snapshot, db_path_text)
    elif page == "因子库":
        _render_library(seed)
    elif page == "数据地图":
        _render_data_map(seed, snapshot)
    elif page == "组合工作台":
        _render_portfolio(seed)
    elif page == "报告中心":
        _render_reports(seed)
    elif page == "监控与告警":
        _render_monitor(seed)
    elif page == "设置":
        _render_settings(seed)


if __name__ == "__main__":
    main()
