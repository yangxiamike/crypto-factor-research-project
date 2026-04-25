from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import site

import numpy as np
import pandas as pd

from factor_research.config import load_yaml_config
from factor_research.evaluation import (
    coverage_ratio,
    decide_profile,
    ic_positive_ratio,
    layered_long_short_return,
    rank_ic,
)
from factor_research.pipeline import run_factor_pipeline

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE_CONFIG_PATH = ROOT / "configs" / "factor_test_profiles.yaml"
DEFAULT_ACCEPTANCE_CONFIG_PATH = ROOT / "configs" / "factor_acceptance.yaml"


class DataInsufficientError(RuntimeError):
    """Raised when DB content is valid but not enough for evaluation."""


@dataclass(frozen=True)
class ProfileEvaluationResult:
    profile: str
    metrics: dict[str, float]
    decision: str
    reasons: list[str]


def _build_decision_config_from_yaml(config_path: Path) -> dict[str, dict[str, float]]:
    raw = load_yaml_config(config_path)
    thresholds = raw.get("thresholds", {})
    if not isinstance(thresholds, dict):
        thresholds = {}
    return {
        "reject_if_below": {
            "coverage_ratio": float(thresholds.get("coverage_ratio_min", 0.70)),
        },
        "watchlist_if_at_least": {
            "rank_ic": float(thresholds.get("rank_ic_mean_min", 0.01)),
            "ic_positive_ratio": float(thresholds.get("ic_positive_ratio_min", 0.50)),
            "long_short_return": 0.0005,
            "coverage_ratio": float(thresholds.get("coverage_ratio_min", 0.80)),
        },
        "pass_if_at_least": {
            "rank_ic": float(thresholds.get("rank_ic_mean_min", 0.02)),
            "ic_positive_ratio": float(thresholds.get("ic_positive_ratio_min", 0.55)),
            "long_short_return": 0.0015,
            "coverage_ratio": float(thresholds.get("coverage_ratio_min", 0.90)),
        },
    }


def _evaluate_profile(frame: pd.DataFrame) -> dict[str, float]:
    daily_ic = pd.Series(
        {
            dt: rank_ic(group["factor"], group["forward_return"])
            for dt, group in frame.groupby("date", sort=True)
        }
    )
    layer_stats = layered_long_short_return(
        data=frame,
        factor_col="factor",
        return_col="forward_return",
        date_col="date",
        n_layers=5,
    )
    return {
        "rank_ic": float(pd.Series(daily_ic).mean(skipna=True)),
        "ic_positive_ratio": ic_positive_ratio(daily_ic, min_count=5),
        "coverage_ratio": coverage_ratio(frame["factor"]),
        "long_short_return": layer_stats["long_short_return"],
    }


def _pick_first(columns: set[str], candidates: list[str], label: str) -> str:
    for c in candidates:
        if c in columns:
            return c
    raise DataInsufficientError(f"未找到 {label} 字段，候选: {candidates}")


def _table_exists(conn: Any, table_name: str) -> bool:
    sql = """
    SELECT COUNT(*) AS c
    FROM information_schema.tables
    WHERE lower(table_name) = lower(?)
    """
    count = conn.execute(sql, [table_name]).fetchone()[0]
    return bool(count)


def _table_columns(conn: Any, table_name: str) -> set[str]:
    info = conn.execute(f"PRAGMA table_info('{table_name}')").fetchdf()
    return set(info["name"].astype(str).tolist())


def _resolve_snapshot_time(snapshot_df: pd.DataFrame, snapshot_col: str, snapshot_time: str | None) -> pd.Timestamp:
    if snapshot_df.empty:
        raise DataInsufficientError("universe_snapshot 为空。")
    ts_series = pd.to_datetime(snapshot_df[snapshot_col], errors="coerce")
    snapshot_df = snapshot_df.assign(_snapshot_ts=ts_series).dropna(subset=["_snapshot_ts"])
    if snapshot_df.empty:
        raise DataInsufficientError("universe_snapshot 的 snapshot_time 无有效时间。")
    if snapshot_time is None:
        return pd.Timestamp(snapshot_df["_snapshot_ts"].max())

    selected = pd.to_datetime(snapshot_time, errors="coerce")
    if pd.isna(selected):
        raise DataInsufficientError(f"--snapshot-time 无法解析: {snapshot_time}")
    return pd.Timestamp(selected)


def _load_universe_members(conn: Any, snapshot_time: str | None) -> tuple[pd.DataFrame, pd.Timestamp]:
    universe, selected_ts, _ = _load_universe_history(conn, snapshot_time)
    latest = universe.loc[universe["_snapshot_ts"] == selected_ts].copy()
    latest = latest.loc[latest["is_member"]].copy()
    if latest.empty:
        raise DataInsufficientError(f"snapshot_time={selected_ts} 没有可用 universe 成分。")
    out = latest[["asset_id", "primary_category"]].drop_duplicates("asset_id")
    return out, selected_ts


def _load_universe_history(conn: Any, snapshot_time: str | None) -> tuple[pd.DataFrame, pd.Timestamp, str]:
    table = "universe_snapshot"
    if not _table_exists(conn, table):
        raise DataInsufficientError("缺少表 universe_snapshot。")
    cols = _table_columns(conn, table)

    asset_col = _pick_first(cols, ["asset_id", "symbol", "exchange_symbol"], "universe 资产标识")
    snapshot_col = _pick_first(
        cols,
        ["snapshot_time", "decision_time", "snapshot_ts", "time", "asof_time"],
        "universe 快照时间",
    )
    member_col = None
    for candidate in ["is_member", "is_in_universe"]:
        if candidate in cols:
            member_col = candidate
            break
    category_col = "primary_category" if "primary_category" in cols else None

    selected_cols = [asset_col, snapshot_col]
    if member_col is not None:
        selected_cols.append(member_col)
    if category_col is not None:
        selected_cols.append(category_col)

    sql = f"SELECT {', '.join(selected_cols)} FROM {table}"
    universe = conn.execute(sql).fetchdf()
    selected_ts = _resolve_snapshot_time(universe, snapshot_col=snapshot_col, snapshot_time=snapshot_time)

    universe = universe.assign(_snapshot_ts=pd.to_datetime(universe[snapshot_col], errors="coerce"))
    universe = universe.dropna(subset=["_snapshot_ts"]).copy()
    universe = universe.loc[universe["_snapshot_ts"] <= selected_ts].copy()
    if member_col is not None:
        universe["is_member"] = universe[member_col].astype(str).str.lower().isin(["true", "1", "t", "yes"])
    else:
        universe["is_member"] = True
    if universe.empty:
        raise DataInsufficientError(f"snapshot_time={selected_ts} 之前没有可用 universe 快照。")

    out = pd.DataFrame({"asset_id": universe[asset_col].astype(str)})
    if category_col is not None:
        out["primary_category"] = universe[category_col].astype(str).fillna("UNKNOWN")
    else:
        out["primary_category"] = "UNKNOWN"
    out["_snapshot_ts"] = universe["_snapshot_ts"]
    out["is_member"] = universe["is_member"].astype(bool)
    out = out.dropna(subset=["asset_id", "_snapshot_ts"])
    if out.empty:
        raise DataInsufficientError("universe_snapshot 资产标识为空。")
    mode = "point_in_time" if int(out["_snapshot_ts"].nunique()) > 1 else "single_snapshot_fallback"
    return out, selected_ts, mode


def _apply_universe_history(
    frame: pd.DataFrame,
    universe_history: pd.DataFrame,
    asset_col: str,
    time_col: str,
    snapshot_ts: pd.Timestamp,
) -> pd.DataFrame:
    frame = frame.loc[frame[time_col] <= snapshot_ts].copy()
    if frame.empty:
        raise DataInsufficientError("snapshot_time 之前没有 market_bars 数据。")

    history = universe_history.copy()
    history["asset_id"] = history["asset_id"].astype(str)
    history["_snapshot_ts"] = pd.to_datetime(history["_snapshot_ts"], errors="coerce")
    history = history.dropna(subset=["asset_id", "_snapshot_ts"])
    if history.empty:
        raise DataInsufficientError("universe_snapshot 历史为空。")

    if int(history["_snapshot_ts"].nunique()) <= 1:
        members = history.loc[history["is_member"], ["asset_id", "primary_category"]].drop_duplicates("asset_id")
        if asset_col == "asset_id":
            out = frame.merge(members, on="asset_id", how="inner")
        else:
            out = frame.merge(members, left_on=asset_col, right_on="asset_id", how="inner")
        if out.empty:
            raise DataInsufficientError("在 snapshot_time 之前没有 market_bars 与 universe 的交集数据。")
        return out

    matched_frames: list[pd.DataFrame] = []
    history_by_asset = {
        asset: group.sort_values("_snapshot_ts")
        for asset, group in history.groupby("asset_id", sort=False)
    }
    for asset, asset_frame in frame.groupby(asset_col, sort=False):
        asset_key = str(asset)
        asset_history = history_by_asset.get(asset_key)
        if asset_history is None or asset_history.empty:
            continue
        left = asset_frame.sort_values(time_col).copy()
        right = asset_history[["_snapshot_ts", "is_member", "primary_category"]].sort_values("_snapshot_ts")
        matched = pd.merge_asof(
            left,
            right,
            left_on=time_col,
            right_on="_snapshot_ts",
            direction="backward",
        )
        matched = matched.loc[matched["is_member"].fillna(False)].copy()
        if not matched.empty:
            matched["asset_id"] = asset_key
            matched_frames.append(matched)

    if not matched_frames:
        raise DataInsufficientError("按历史 universe 快照过滤后没有可用 market_bars。")
    return pd.concat(matched_frames, ignore_index=True)


def _load_market_bars(conn: Any) -> tuple[pd.DataFrame, str, str, str, str | None]:
    table = "market_bars"
    if not _table_exists(conn, table):
        raise DataInsufficientError("缺少表 market_bars。")
    cols = _table_columns(conn, table)

    asset_col = _pick_first(cols, ["asset_id", "symbol", "exchange_symbol"], "market_bars 资产标识")
    time_col = _pick_first(
        cols,
        ["bar_time", "close_time", "ts", "timestamp", "time", "open_time"],
        "market_bars 时间",
    )
    close_col = _pick_first(cols, ["close", "close_price", "price", "last_price"], "market_bars 收盘价")
    volume_col = None
    for c in ["quote_volume", "volume", "base_volume"]:
        if c in cols:
            volume_col = c
            break

    selected_cols = [asset_col, time_col, close_col]
    if volume_col is not None:
        selected_cols.append(volume_col)
    sql = f"SELECT {', '.join(selected_cols)} FROM {table}"
    bars = conn.execute(sql).fetchdf()
    if bars.empty:
        raise DataInsufficientError("market_bars 为空。")
    return bars, asset_col, time_col, close_col, volume_col


def _prepare_pipeline_input(
    universe_history: pd.DataFrame,
    bars: pd.DataFrame,
    asset_col: str,
    time_col: str,
    close_col: str,
    volume_col: str | None,
    snapshot_ts: pd.Timestamp,
    horizon_hours: int,
) -> pd.DataFrame:
    frame = bars.copy()
    frame[asset_col] = frame[asset_col].astype(str)
    frame[time_col] = pd.to_datetime(frame[time_col], errors="coerce")
    frame[close_col] = pd.to_numeric(frame[close_col], errors="coerce")
    frame = frame.dropna(subset=[asset_col, time_col, close_col])
    frame = frame.loc[frame[close_col] > 0].copy()
    frame = _apply_universe_history(
        frame=frame,
        universe_history=universe_history,
        asset_col=asset_col,
        time_col=time_col,
        snapshot_ts=snapshot_ts,
    )

    frame = frame.sort_values(["asset_id", time_col], ascending=True).copy()
    frame["ret_1"] = frame.groupby("asset_id")[close_col].pct_change()
    frame["raw_factor"] = np.log(frame[close_col] / frame.groupby("asset_id")[close_col].shift(horizon_hours))
    frame["forward_return"] = (
        frame.groupby("asset_id")[close_col].shift(-horizon_hours) / frame[close_col] - 1.0
    )
    frame["beta"] = frame.groupby("asset_id")["ret_1"].transform(
        lambda x: x.rolling(24, min_periods=6).mean()
    )
    frame["size"] = np.log(frame[close_col].clip(lower=1e-12))
    if volume_col is None:
        quote_volume = pd.Series(0.0, index=frame.index, dtype=float)
    else:
        base_volume = pd.to_numeric(frame[volume_col], errors="coerce").fillna(0.0)
        if volume_col == "quote_volume":
            quote_volume = base_volume
        else:
            quote_volume = base_volume * frame[close_col]
    frame["liquidity"] = np.log1p(quote_volume.clip(lower=0.0))
    frame["volatility"] = frame.groupby("asset_id")["ret_1"].transform(
        lambda x: x.rolling(24, min_periods=6).std()
    )
    frame["age"] = frame.groupby("asset_id").cumcount() + 1
    frame["date"] = frame[time_col]

    required = ["date", "asset_id", "forward_return", "raw_factor", "primary_category"]
    out = frame[
        required
        + [
            "beta",
            "size",
            "liquidity",
            "volatility",
            "age",
        ]
    ].copy()
    out = out.dropna(subset=["date", "asset_id", "raw_factor", "forward_return"])
    if out.empty:
        raise DataInsufficientError("可用于计算的样本为空（raw_factor/forward_return 全缺失）。")
    return out


def _build_pipeline_profile(profile_name: str, profile_cfg: Mapping[str, Any], available_cols: set[str]) -> dict[str, Any]:
    exposure_cols = [c for c in profile_cfg.get("neutralize_exposures", []) if c in available_cols]
    categorical_cols = ["primary_category"] if "primary_category" in exposure_cols else []
    group_col = profile_cfg.get("group_by") if profile_cfg.get("within_category") else None
    if group_col not in available_cols:
        group_col = None

    return {
        "factor_col": "raw_factor",
        "date_col": "date",
        "preprocess": {
            "winsorize": True,
            "n_mad": 5.0,
            "standardize": "zscore",
        },
        "neutralize": {
            "enabled": bool(exposure_cols),
            "exposure_cols": exposure_cols,
            "categorical_cols": categorical_cols,
            "min_obs": 10,
            "add_intercept": True,
        },
        "orthogonalize": {
            "enabled": False,
            "benchmark_cols": [],
        },
        "profile_name": profile_name,
        "group_col": group_col,
    }


def _build_working_frame(frame: pd.DataFrame, group_col: str | None) -> tuple[pd.DataFrame, str]:
    if group_col is None:
        return frame, "date"
    out = frame.copy()
    out["_group_date"] = out["date"].astype("string") + "|" + out[group_col].astype("string")
    return out, "_group_date"


def run_v1_from_db(
    db_path: str | Path,
    snapshot_time: str | None = None,
    horizon_hours: int = 24,
    profile_config_path: str | Path = DEFAULT_PROFILE_CONFIG_PATH,
    acceptance_config_path: str | Path = DEFAULT_ACCEPTANCE_CONFIG_PATH,
) -> tuple[list[ProfileEvaluationResult], dict[str, Any]]:
    if horizon_hours <= 0:
        raise ValueError("horizon_hours 必须 > 0")

    try:
        site.addsitedir(site.getusersitepackages())
        import duckdb
    except ImportError as exc:
        raise DataInsufficientError("缺少 duckdb 依赖，请先安装 duckdb。") from exc

    profile_cfg = load_yaml_config(profile_config_path).get("profiles", {})
    if not isinstance(profile_cfg, dict) or not profile_cfg:
        raise DataInsufficientError("profiles 配置为空。")
    decision_cfg = _build_decision_config_from_yaml(Path(acceptance_config_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        universe_history, selected_ts, universe_mode = _load_universe_history(conn, snapshot_time=snapshot_time)
        bars, asset_col, time_col, close_col, volume_col = _load_market_bars(conn)
        pipeline_input = _prepare_pipeline_input(
            universe_history=universe_history,
            bars=bars,
            asset_col=asset_col,
            time_col=time_col,
            close_col=close_col,
            volume_col=volume_col,
            snapshot_ts=selected_ts,
            horizon_hours=horizon_hours,
        )

        unique_dates = int(pipeline_input["date"].nunique())
        unique_assets = int(pipeline_input["asset_id"].nunique())
        if unique_dates < 2 or unique_assets < 5:
            raise DataInsufficientError(
                f"样本不足：dates={unique_dates}, assets={unique_assets}，至少需要 2 个时间截面和 5 个资产。"
            )

        results: list[ProfileEvaluationResult] = []
        for profile_name, cfg in profile_cfg.items():
            if not isinstance(cfg, Mapping):
                continue
            runtime_profile = _build_pipeline_profile(profile_name, cfg, set(pipeline_input.columns))
            working, date_col = _build_working_frame(pipeline_input, runtime_profile.get("group_col"))
            runtime_profile["date_col"] = date_col
            pipeline_result = run_factor_pipeline(working, runtime_profile)

            eval_frame = pipeline_input[["date", "asset_id", "forward_return"]].copy()
            eval_frame["factor"] = pipeline_result["frame"]["final"]
            eval_frame = eval_frame.dropna(subset=["factor", "forward_return"])
            if eval_frame.empty:
                metrics = {
                    "rank_ic": float("nan"),
                    "ic_positive_ratio": float("nan"),
                    "coverage_ratio": 0.0,
                    "long_short_return": float("nan"),
                }
            else:
                metrics = _evaluate_profile(eval_frame)
            decision = decide_profile(metrics, config=decision_cfg)
            results.append(
                ProfileEvaluationResult(
                    profile=profile_name,
                    metrics=metrics,
                    decision=decision.label,
                    reasons=decision.reasons,
                )
            )

        meta = {
            "snapshot_time": str(selected_ts),
            "horizon_hours": int(horizon_hours),
            "rows": int(len(pipeline_input)),
            "n_dates": unique_dates,
            "n_assets": unique_assets,
            "universe_mode": universe_mode,
        }
        return results, meta
    finally:
        conn.close()
