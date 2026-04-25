from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import json
import site
import uuid

import numpy as np
import pandas as pd

from factor_research.config import load_yaml_config
from factor_research.evaluation import decide_profile
from factor_research.pipeline import run_factor_pipeline
from factor_research.runtime.from_db import (
    DEFAULT_ACCEPTANCE_CONFIG_PATH,
    DEFAULT_PROFILE_CONFIG_PATH,
    DataInsufficientError,
    _build_decision_config_from_yaml,
    _build_pipeline_profile,
    _build_working_frame,
    _evaluate_profile,
    _apply_universe_history,
    _load_market_bars,
    _load_universe_history,
    _table_columns,
)

from .formulas import FormulaExecutionError, compute_raw_factor
from .schemas import AgentFactorTask, AgentTaskValidationError, load_agent_task_payload, parse_agent_task


@dataclass(frozen=True)
class AgentTaskResult:
    task_id: str
    factor_name: str
    input_status: str
    status: str
    execution_status: str
    message: str
    executed_profiles: int


@dataclass(frozen=True)
class AgentBatchResult:
    run_id: str
    snapshot_time: str
    universe_mode: str
    tasks_total: int
    tasks_approved: int
    summary_by_execution: dict[str, int]
    task_results: list[AgentTaskResult]


TASK_TABLE_SCHEMA: dict[str, str] = {
    "run_id": "VARCHAR",
    "task_id": "VARCHAR",
    "factor_name": "VARCHAR",
    "hypothesis": "VARCHAR",
    "required_fields_json": "VARCHAR",
    "formula_draft": "VARCHAR",
    "formula_key": "VARCHAR",
    "formula_params_json": "VARCHAR",
    "direction": "VARCHAR",
    "horizons_json": "VARCHAR",
    "neutralization_profile_json": "VARCHAR",
    "risk_checks_json": "VARCHAR",
    "acceptance_rule_version": "VARCHAR",
    "input_status": "VARCHAR",
    "status": "VARCHAR",
    "execution_status": "VARCHAR",
    "message": "VARCHAR",
    "created_at": "TIMESTAMP",
}

EXPERIMENT_TABLE_SCHEMA: dict[str, str] = {
    "run_id": "VARCHAR",
    "task_id": "VARCHAR",
    "factor_name": "VARCHAR",
    "horizon_hours": "INTEGER",
    "profile_name": "VARCHAR",
    "status": "VARCHAR",
    "decision": "VARCHAR",
    "reasons_json": "VARCHAR",
    "sample_rows": "BIGINT",
    "n_dates": "INTEGER",
    "n_assets": "INTEGER",
    "error_message": "VARCHAR",
    "created_at": "TIMESTAMP",
}

EVALUATION_TABLE_SCHEMA: dict[str, str] = {
    "run_id": "VARCHAR",
    "task_id": "VARCHAR",
    "factor_name": "VARCHAR",
    "horizon_hours": "INTEGER",
    "profile_name": "VARCHAR",
    "rank_ic": "DOUBLE",
    "ic_positive_ratio": "DOUBLE",
    "coverage_ratio": "DOUBLE",
    "long_short_return": "DOUBLE",
    "status": "VARCHAR",
    "evaluation_time": "TIMESTAMP",
    "created_at": "TIMESTAMP",
}

DECISION_TABLE_SCHEMA: dict[str, str] = {
    "run_id": "VARCHAR",
    "task_id": "VARCHAR",
    "factor_name": "VARCHAR",
    "horizon_hours": "INTEGER",
    "profile_name": "VARCHAR",
    "decision": "VARCHAR",
    "reasons_json": "VARCHAR",
    "acceptance_rule_version": "VARCHAR",
    "status": "VARCHAR",
    "decision_time": "TIMESTAMP",
    "created_at": "TIMESTAMP",
}


def run_agent_factor_tasks(
    db_path: str | Path,
    tasks_config_path: str | Path,
    snapshot_time: str | None = None,
    default_horizon_hours: int = 8,
    profile_config_path: str | Path = DEFAULT_PROFILE_CONFIG_PATH,
    acceptance_config_path: str | Path = DEFAULT_ACCEPTANCE_CONFIG_PATH,
) -> AgentBatchResult:
    if default_horizon_hours <= 0:
        raise ValueError("default_horizon_hours 必须 > 0")

    try:
        site.addsitedir(site.getusersitepackages())
        import duckdb
    except ImportError as exc:
        raise DataInsufficientError("缺少 duckdb 依赖，请先安装 duckdb。") from exc

    raw_tasks = load_agent_task_payload(tasks_config_path)
    run_id = f"agent_run_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    now = _utcnow_naive()
    decision_cfg = _build_decision_config_from_yaml(Path(acceptance_config_path))

    profile_cfg = load_yaml_config(profile_config_path).get("profiles", {})
    if not isinstance(profile_cfg, dict) or not profile_cfg:
        raise DataInsufficientError("profiles 配置为空。")

    conn = duckdb.connect(str(db_path))
    try:
        _ensure_all_tables(conn)

        universe_history, selected_ts, universe_mode = _load_universe_history(conn, snapshot_time=snapshot_time)
        bars, asset_col, time_col, close_col, volume_col = _load_market_bars(conn)
        market_columns = _table_columns(conn, "market_bars")
        base_frame = _prepare_base_frame(
            universe_history=universe_history,
            bars=bars,
            asset_col=asset_col,
            time_col=time_col,
            close_col=close_col,
            volume_col=volume_col,
            snapshot_ts=selected_ts,
        )
        _assert_base_sample(base_frame)

        task_rows: list[dict[str, Any]] = []
        experiment_rows: list[dict[str, Any]] = []
        evaluation_rows: list[dict[str, Any]] = []
        decision_rows: list[dict[str, Any]] = []
        task_results: list[AgentTaskResult] = []
        seen_task_ids: set[str] = set()

        for raw in raw_tasks:
            parsed, parse_message = _try_parse_task(raw, default_horizon_hours=default_horizon_hours)
            if parsed is None:
                task_id = str(raw.get("task_id") or f"invalid_{uuid.uuid4().hex[:8]}")
                factor_name = str(raw.get("factor_name") or "UNKNOWN")
                task_row, result_row = _build_failed_parse_rows(
                    run_id=run_id,
                    now=now,
                    task_id=task_id,
                    factor_name=factor_name,
                    message=parse_message,
                )
                task_rows.append(task_row)
                task_results.append(result_row)
                experiment_rows.append(
                    _build_experiment_row(
                        run_id=run_id,
                        now=now,
                        task_id=task_id,
                        factor_name=factor_name,
                        status="failed",
                        error_message=parse_message,
                    )
                )
                continue

            if parsed.task_id in seen_task_ids:
                dup_message = f"task_id 重复: {parsed.task_id}"
                task_rows.append(
                    _build_task_row(
                        run_id=run_id,
                        now=now,
                        task=parsed,
                        status="failed",
                        execution_status="failed",
                        message=dup_message,
                    )
                )
                task_results.append(
                    AgentTaskResult(
                        task_id=parsed.task_id,
                        factor_name=parsed.factor_name,
                        input_status=parsed.status,
                        status="failed",
                        execution_status="failed",
                        message=dup_message,
                        executed_profiles=0,
                    )
                )
                experiment_rows.append(
                    _build_experiment_row(
                        run_id=run_id,
                        now=now,
                        task_id=parsed.task_id,
                        factor_name=parsed.factor_name,
                        status="failed",
                        error_message=dup_message,
                    )
                )
                continue
            seen_task_ids.add(parsed.task_id)

            result = _run_single_task(
                task=parsed,
                run_id=run_id,
                now=now,
                market_columns=market_columns,
                base_frame=base_frame,
                close_col=close_col,
                volume_col=volume_col,
                profile_cfg=profile_cfg,
                decision_cfg=decision_cfg,
            )
            task_rows.append(result["task_row"])
            experiment_rows.extend(result["experiment_rows"])
            evaluation_rows.extend(result["evaluation_rows"])
            decision_rows.extend(result["decision_rows"])
            task_results.append(result["task_result"])

        _append_rows(conn, "agent_factor_tasks", task_rows, TASK_TABLE_SCHEMA)
        _append_rows(conn, "agent_factor_experiments", experiment_rows, EXPERIMENT_TABLE_SCHEMA)
        _append_rows(conn, "factor_evaluation", evaluation_rows, EVALUATION_TABLE_SCHEMA)
        _append_rows(conn, "factor_decision", decision_rows, DECISION_TABLE_SCHEMA)

        summary = _build_summary(task_results)
        approved_count = int(sum(1 for x in task_results if x.input_status == "approved"))
        return AgentBatchResult(
            run_id=run_id,
            snapshot_time=str(selected_ts),
            universe_mode=universe_mode,
            tasks_total=len(task_results),
            tasks_approved=approved_count,
            summary_by_execution=summary,
            task_results=task_results,
        )
    finally:
        conn.close()


def _try_parse_task(
    raw: Mapping[str, Any],
    default_horizon_hours: int,
) -> tuple[AgentFactorTask | None, str]:
    try:
        task = parse_agent_task(raw, default_horizon_hours=default_horizon_hours)
        return task, ""
    except AgentTaskValidationError as exc:
        return None, str(exc)


def _build_failed_parse_rows(
    run_id: str,
    now: pd.Timestamp,
    task_id: str,
    factor_name: str,
    message: str,
) -> tuple[dict[str, Any], AgentTaskResult]:
    task_row = {
        "run_id": run_id,
        "task_id": task_id,
        "factor_name": factor_name,
        "hypothesis": "",
        "required_fields_json": "[]",
        "formula_draft": "",
        "formula_key": "",
        "formula_params_json": "{}",
        "direction": "",
        "horizons_json": "[]",
        "neutralization_profile_json": "[]",
        "risk_checks_json": "[]",
        "acceptance_rule_version": "",
        "input_status": "failed",
        "status": "failed",
        "execution_status": "failed",
        "message": message,
        "created_at": now,
    }
    result_row = AgentTaskResult(
        task_id=task_id,
        factor_name=factor_name,
        input_status="failed",
        status="failed",
        execution_status="failed",
        message=message,
        executed_profiles=0,
    )
    return task_row, result_row


def _run_single_task(
    task: AgentFactorTask,
    run_id: str,
    now: pd.Timestamp,
    market_columns: set[str],
    base_frame: pd.DataFrame,
    close_col: str,
    volume_col: str | None,
    profile_cfg: Mapping[str, Any],
    decision_cfg: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    experiment_rows: list[dict[str, Any]] = []
    evaluation_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []

    if task.status != "approved":
        message = f"状态为 {task.status}，已跳过。"
        experiment_rows.append(
            _build_experiment_row(
                run_id=run_id,
                now=now,
                task_id=task.task_id,
                factor_name=task.factor_name,
                status="skipped",
                error_message=message,
            )
        )
        return {
            "task_row": _build_task_row(
                run_id=run_id,
                now=now,
                task=task,
                status=task.status,
                execution_status="skipped",
                message=message,
            ),
            "experiment_rows": experiment_rows,
            "evaluation_rows": evaluation_rows,
            "decision_rows": decision_rows,
            "task_result": AgentTaskResult(
                task_id=task.task_id,
                factor_name=task.factor_name,
                input_status=task.status,
                status=task.status,
                execution_status="skipped",
                message=message,
                executed_profiles=0,
            ),
        }

    missing_fields = _missing_required_fields(task.required_fields, market_columns)
    formula_block_reasons = _formula_field_readiness_issue(task.formula_key, volume_col=volume_col)
    if missing_fields or formula_block_reasons:
        reasons: list[str] = []
        if missing_fields:
            reasons.append("缺少字段: " + ", ".join(missing_fields))
        reasons.extend(formula_block_reasons)
        message = "；".join(reasons)
        experiment_rows.append(
            _build_experiment_row(
                run_id=run_id,
                now=now,
                task_id=task.task_id,
                factor_name=task.factor_name,
                status="blocked",
                error_message=message,
            )
        )
        return {
            "task_row": _build_task_row(
                run_id=run_id,
                now=now,
                task=task,
                status="blocked",
                execution_status="blocked",
                message=message,
            ),
            "experiment_rows": experiment_rows,
            "evaluation_rows": evaluation_rows,
            "decision_rows": decision_rows,
            "task_result": AgentTaskResult(
                task_id=task.task_id,
                factor_name=task.factor_name,
                input_status=task.status,
                status="blocked",
                execution_status="blocked",
                message=message,
                executed_profiles=0,
            ),
        }

    try:
        raw_factor = compute_raw_factor(
            frame=base_frame,
            formula_key=task.formula_key,
            formula_params=task.formula_params,
            direction=task.direction,
            asset_col="asset_id",
            close_col=close_col,
            volume_col=volume_col,
        )
    except FormulaExecutionError as exc:
        message = str(exc)
        experiment_rows.append(
            _build_experiment_row(
                run_id=run_id,
                now=now,
                task_id=task.task_id,
                factor_name=task.factor_name,
                status="failed",
                error_message=message,
            )
        )
        return {
            "task_row": _build_task_row(
                run_id=run_id,
                now=now,
                task=task,
                status="failed",
                execution_status="failed",
                message=message,
            ),
            "experiment_rows": experiment_rows,
            "evaluation_rows": evaluation_rows,
            "decision_rows": decision_rows,
            "task_result": AgentTaskResult(
                task_id=task.task_id,
                factor_name=task.factor_name,
                input_status=task.status,
                status="failed",
                execution_status="failed",
                message=message,
                executed_profiles=0,
            ),
        }

    selected_profiles, unknown_profiles = _resolve_profiles(
        task.neutralization_profile, profile_cfg
    )
    if unknown_profiles:
        message = "未知 profile: " + ", ".join(unknown_profiles)
        experiment_rows.append(
            _build_experiment_row(
                run_id=run_id,
                now=now,
                task_id=task.task_id,
                factor_name=task.factor_name,
                status="failed",
                error_message=message,
            )
        )
        return {
            "task_row": _build_task_row(
                run_id=run_id,
                now=now,
                task=task,
                status="failed",
                execution_status="failed",
                message=message,
            ),
            "experiment_rows": experiment_rows,
            "evaluation_rows": evaluation_rows,
            "decision_rows": decision_rows,
            "task_result": AgentTaskResult(
                task_id=task.task_id,
                factor_name=task.factor_name,
                input_status=task.status,
                status="failed",
                execution_status="failed",
                message=message,
                executed_profiles=0,
            ),
        }

    executed_profiles = 0
    blocked_messages: list[str] = []
    failed_messages: list[str] = []

    for horizon in task.horizons:
        try:
            horizon_frame = _build_horizon_frame(
                base_frame=base_frame,
                raw_factor=raw_factor,
                close_col=close_col,
                horizon_hours=horizon,
            )
            _assert_horizon_sample(horizon_frame, horizon=horizon)
        except DataInsufficientError as exc:
            blocked_messages.append(f"h={horizon}: {exc}")
            experiment_rows.append(
                _build_experiment_row(
                    run_id=run_id,
                    now=now,
                    task_id=task.task_id,
                    factor_name=task.factor_name,
                    status="blocked",
                    horizon_hours=horizon,
                    error_message=str(exc),
                )
            )
            continue

        for profile_name in selected_profiles:
            cfg = profile_cfg.get(profile_name)
            if not isinstance(cfg, Mapping):
                failed_message = f"profile 配置非法: {profile_name}"
                failed_messages.append(failed_message)
                experiment_rows.append(
                    _build_experiment_row(
                        run_id=run_id,
                        now=now,
                        task_id=task.task_id,
                        factor_name=task.factor_name,
                        horizon_hours=horizon,
                        profile_name=profile_name,
                        status="failed",
                        error_message=failed_message,
                    )
                )
                continue

            try:
                runtime_profile = _build_pipeline_profile(
                    profile_name, cfg, set(horizon_frame.columns)
                )
                working, date_col = _build_working_frame(
                    horizon_frame, runtime_profile.get("group_col")
                )
                runtime_profile["date_col"] = date_col
                pipeline_result = run_factor_pipeline(working, runtime_profile)

                eval_frame = horizon_frame[["date", "asset_id", "forward_return"]].copy()
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

                evaluation_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task.task_id,
                        "factor_name": task.factor_name,
                        "horizon_hours": horizon,
                        "profile_name": profile_name,
                        "rank_ic": metrics.get("rank_ic"),
                        "ic_positive_ratio": metrics.get("ic_positive_ratio"),
                        "coverage_ratio": metrics.get("coverage_ratio"),
                        "long_short_return": metrics.get("long_short_return"),
                        "status": "executed",
                        "evaluation_time": now,
                        "created_at": now,
                    }
                )
                decision_rows.append(
                    {
                        "run_id": run_id,
                        "task_id": task.task_id,
                        "factor_name": task.factor_name,
                        "horizon_hours": horizon,
                        "profile_name": profile_name,
                        "decision": decision.label,
                        "reasons_json": _json_dumps(decision.reasons),
                        "acceptance_rule_version": task.acceptance_rule_version,
                        "status": "executed",
                        "decision_time": now,
                        "created_at": now,
                    }
                )
                experiment_rows.append(
                    _build_experiment_row(
                        run_id=run_id,
                        now=now,
                        task_id=task.task_id,
                        factor_name=task.factor_name,
                        horizon_hours=horizon,
                        profile_name=profile_name,
                        status="executed",
                        decision=decision.label,
                        reasons=decision.reasons,
                        sample_rows=int(len(horizon_frame)),
                        n_dates=int(horizon_frame["date"].nunique()),
                        n_assets=int(horizon_frame["asset_id"].nunique()),
                    )
                )
                executed_profiles += 1
            except Exception as exc:  # pragma: no cover - defensive continuation
                failed_message = f"h={horizon}, profile={profile_name}, error={exc}"
                failed_messages.append(failed_message)
                experiment_rows.append(
                    _build_experiment_row(
                        run_id=run_id,
                        now=now,
                        task_id=task.task_id,
                        factor_name=task.factor_name,
                        horizon_hours=horizon,
                        profile_name=profile_name,
                        status="failed",
                        error_message=str(exc),
                    )
                )

    if executed_profiles > 0:
        status = "executed"
        execution_status = "executed"
        message = f"执行成功，profile_runs={executed_profiles}"
    elif blocked_messages and not failed_messages:
        status = "blocked"
        execution_status = "blocked"
        message = "；".join(dict.fromkeys(blocked_messages))
    else:
        status = "failed"
        execution_status = "failed"
        merged = blocked_messages + failed_messages
        message = "；".join(dict.fromkeys(merged)) if merged else "未产生可用结果"

    return {
        "task_row": _build_task_row(
            run_id=run_id,
            now=now,
            task=task,
            status=status,
            execution_status=execution_status,
            message=message,
        ),
        "experiment_rows": experiment_rows,
        "evaluation_rows": evaluation_rows,
        "decision_rows": decision_rows,
        "task_result": AgentTaskResult(
            task_id=task.task_id,
            factor_name=task.factor_name,
            input_status=task.status,
            status=status,
            execution_status=execution_status,
            message=message,
            executed_profiles=executed_profiles,
        ),
    }


def _build_task_row(
    run_id: str,
    now: pd.Timestamp,
    task: AgentFactorTask,
    status: str,
    execution_status: str,
    message: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task_id": task.task_id,
        "factor_name": task.factor_name,
        "hypothesis": task.hypothesis,
        "required_fields_json": _json_dumps(task.required_fields),
        "formula_draft": task.formula_draft,
        "formula_key": task.formula_key,
        "formula_params_json": _json_dumps(task.formula_params),
        "direction": task.direction,
        "horizons_json": _json_dumps(task.horizons),
        "neutralization_profile_json": _json_dumps(task.neutralization_profile),
        "risk_checks_json": _json_dumps(task.risk_checks),
        "acceptance_rule_version": task.acceptance_rule_version,
        "input_status": task.status,
        "status": status,
        "execution_status": execution_status,
        "message": message,
        "created_at": now,
    }


def _build_experiment_row(
    run_id: str,
    now: pd.Timestamp,
    task_id: str,
    factor_name: str,
    status: str,
    horizon_hours: int | None = None,
    profile_name: str | None = None,
    decision: str | None = None,
    reasons: list[str] | None = None,
    sample_rows: int | None = None,
    n_dates: int | None = None,
    n_assets: int | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task_id": task_id,
        "factor_name": factor_name,
        "horizon_hours": horizon_hours,
        "profile_name": profile_name,
        "status": status,
        "decision": decision,
        "reasons_json": _json_dumps(reasons or []),
        "sample_rows": sample_rows,
        "n_dates": n_dates,
        "n_assets": n_assets,
        "error_message": error_message,
        "created_at": now,
    }


def _prepare_base_frame(
    universe_history: pd.DataFrame,
    bars: pd.DataFrame,
    asset_col: str,
    time_col: str,
    close_col: str,
    volume_col: str | None,
    snapshot_ts: pd.Timestamp,
) -> pd.DataFrame:
    frame = bars.copy()
    frame[asset_col] = frame[asset_col].astype(str)
    frame[time_col] = pd.to_datetime(frame[time_col], errors="coerce")
    frame[close_col] = pd.to_numeric(frame[close_col], errors="coerce")
    if volume_col is not None and volume_col in frame.columns:
        frame[volume_col] = pd.to_numeric(frame[volume_col], errors="coerce")
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
    frame["date"] = frame[time_col]
    frame["ret_1"] = frame.groupby("asset_id")[close_col].pct_change()
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
    return frame


def _build_horizon_frame(
    base_frame: pd.DataFrame,
    raw_factor: pd.Series,
    close_col: str,
    horizon_hours: int,
) -> pd.DataFrame:
    if horizon_hours <= 0:
        raise DataInsufficientError("horizon_hours 必须 > 0")
    out = base_frame[
        [
            "date",
            "asset_id",
            "primary_category",
            "beta",
            "size",
            "liquidity",
            "volatility",
            "age",
        ]
    ].copy()
    out["raw_factor"] = raw_factor
    out["forward_return"] = (
        base_frame.groupby("asset_id")[close_col].shift(-horizon_hours) / base_frame[close_col]
        - 1.0
    )
    out = out.dropna(subset=["date", "asset_id", "raw_factor", "forward_return"])
    if out.empty:
        raise DataInsufficientError("horizon 样本为空。")
    return out


def _assert_base_sample(base_frame: pd.DataFrame) -> None:
    n_dates = int(base_frame["date"].nunique())
    n_assets = int(base_frame["asset_id"].nunique())
    if n_dates < 2 or n_assets < 5:
        raise DataInsufficientError(
            f"样本不足：dates={n_dates}, assets={n_assets}，至少需要 2 个时间截面和 5 个资产。"
        )


def _assert_horizon_sample(frame: pd.DataFrame, horizon: int) -> None:
    n_dates = int(frame["date"].nunique())
    n_assets = int(frame["asset_id"].nunique())
    if n_dates < 2 or n_assets < 5:
        raise DataInsufficientError(
            f"horizon={horizon} 样本不足：dates={n_dates}, assets={n_assets}"
        )


def _resolve_profiles(
    requested_profiles: list[str],
    profile_cfg: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    available = list(profile_cfg.keys())
    if not requested_profiles:
        return available, []
    if any(x.lower() in {"all", "*"} for x in requested_profiles):
        return available, []
    selected: list[str] = []
    unknown: list[str] = []
    for profile in requested_profiles:
        if profile in profile_cfg:
            if profile not in selected:
                selected.append(profile)
        else:
            unknown.append(profile)
    return selected, unknown


def _missing_required_fields(required_fields: list[str], market_columns: set[str]) -> list[str]:
    if not required_fields:
        return []
    lower_to_real = {c.lower(): c for c in market_columns}
    missing: list[str] = []
    for field in required_fields:
        if field.lower() not in lower_to_real:
            missing.append(field)
    return missing


def _formula_field_readiness_issue(formula_key: str, volume_col: str | None) -> list[str]:
    if formula_key != "volume_zscore":
        return []
    if volume_col is None:
        return ["volume_zscore 需要 volume 或 quote_volume 字段。"]
    return []


def _ensure_all_tables(conn: Any) -> None:
    _ensure_table(conn, "agent_factor_tasks", TASK_TABLE_SCHEMA)
    _ensure_table(conn, "agent_factor_experiments", EXPERIMENT_TABLE_SCHEMA)
    _ensure_table(conn, "factor_evaluation", EVALUATION_TABLE_SCHEMA)
    _ensure_table(conn, "factor_decision", DECISION_TABLE_SCHEMA)


def _ensure_table(conn: Any, table_name: str, schema: Mapping[str, str]) -> None:
    ordered_cols = [f'"{k}" {v}' for k, v in schema.items()]
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n  '
        + ",\n  ".join(ordered_cols)
        + "\n)"
    )
    existing = _table_columns(conn, table_name)
    for name, dtype in schema.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {dtype}')


def _append_rows(
    conn: Any,
    table_name: str,
    rows: list[dict[str, Any]],
    schema: Mapping[str, str],
) -> int:
    if not rows:
        return 0
    columns = list(schema.keys())
    frame = pd.DataFrame(rows)
    for col in columns:
        if col not in frame.columns:
            frame[col] = None
    frame = frame[columns].copy()
    tmp_name = f"_tmp_{table_name}_{uuid.uuid4().hex[:8]}"
    conn.register(tmp_name, frame)
    try:
        quoted = ", ".join(f'"{c}"' for c in columns)
        conn.execute(
            f'INSERT INTO "{table_name}" ({quoted}) SELECT {quoted} FROM "{tmp_name}"'
        )
    finally:
        conn.unregister(tmp_name)
    return int(len(frame))


def _build_summary(task_results: list[AgentTaskResult]) -> dict[str, int]:
    summary: dict[str, int] = {
        "executed": 0,
        "skipped": 0,
        "blocked": 0,
        "failed": 0,
    }
    for row in task_results:
        key = row.execution_status
        if key not in summary:
            summary[key] = 0
        summary[key] += 1
    return summary


def _utcnow_naive() -> pd.Timestamp:
    return pd.Timestamp.utcnow().tz_localize(None)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
