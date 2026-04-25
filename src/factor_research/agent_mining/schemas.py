from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import re

from factor_research.config import load_yaml_config


ALLOWED_TASK_STATUSES: frozenset[str] = frozenset(
    {"draft", "approved", "rejected", "executed", "blocked", "failed"}
)
ALLOWED_DIRECTIONS: frozenset[str] = frozenset({"positive", "negative"})
ALLOWED_FORMULA_KEYS: frozenset[str] = frozenset(
    {"close_momentum", "volume_zscore", "volatility"}
)


class AgentTaskValidationError(ValueError):
    """Raised when agent task payload is invalid."""


@dataclass(frozen=True)
class AgentFactorTask:
    task_id: str
    factor_name: str
    hypothesis: str
    required_fields: list[str]
    formula_draft: str
    formula_key: str
    formula_params: dict[str, Any]
    direction: str
    horizons: list[int]
    neutralization_profile: list[str]
    risk_checks: list[str]
    acceptance_rule_version: str
    status: str


def load_agent_task_payload(path: str | Path) -> list[Mapping[str, Any]]:
    payload = load_yaml_config(path)
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise AgentTaskValidationError("任务配置必须包含 tasks 列表。")
    out: list[Mapping[str, Any]] = []
    for item in tasks:
        if not isinstance(item, Mapping):
            raise AgentTaskValidationError("tasks 中每个任务都必须是字典对象。")
        out.append(item)
    return out


def parse_agent_task(raw: Mapping[str, Any], default_horizon_hours: int) -> AgentFactorTask:
    task_id = _read_non_empty_string(raw, "task_id")
    factor_name = _read_non_empty_string(raw, "factor_name")
    hypothesis = _read_non_empty_string(raw, "hypothesis")
    formula_draft = _read_non_empty_string(raw, "formula_draft")
    formula_key = _read_non_empty_string(raw, "formula_key").lower()
    if formula_key not in ALLOWED_FORMULA_KEYS:
        raise AgentTaskValidationError(
            f"task_id={task_id} formula_key 不在白名单: {formula_key}"
        )

    direction = _read_non_empty_string(raw, "direction").lower()
    if direction not in ALLOWED_DIRECTIONS:
        raise AgentTaskValidationError(
            f"task_id={task_id} direction 必须是 positive/negative。"
        )

    status = _read_non_empty_string(raw, "status").lower()
    if status not in ALLOWED_TASK_STATUSES:
        raise AgentTaskValidationError(
            f"task_id={task_id} status 不合法: {status}"
        )

    formula_params = _read_mapping(raw.get("formula_params"), "formula_params", task_id)
    window = formula_params.get("window")
    if window is None:
        formula_params["window"] = 24
    else:
        window_value = _parse_positive_int(window, label="window", task_id=task_id)
        formula_params["window"] = window_value

    horizons = _parse_horizons(raw.get("horizons"), default_horizon_hours, task_id=task_id)

    required_fields = _read_string_list(raw.get("required_fields"), "required_fields", task_id=task_id)
    neutralization_profile = _read_string_list(
        raw.get("neutralization_profile"),
        "neutralization_profile",
        task_id=task_id,
    )
    risk_checks = _read_string_list(raw.get("risk_checks"), "risk_checks", task_id=task_id)
    acceptance_rule_version = _read_non_empty_string(raw, "acceptance_rule_version")

    return AgentFactorTask(
        task_id=task_id,
        factor_name=factor_name,
        hypothesis=hypothesis,
        required_fields=required_fields,
        formula_draft=formula_draft,
        formula_key=formula_key,
        formula_params=formula_params,
        direction=direction,
        horizons=horizons,
        neutralization_profile=neutralization_profile,
        risk_checks=risk_checks,
        acceptance_rule_version=acceptance_rule_version,
        status=status,
    )


def _read_non_empty_string(raw: Mapping[str, Any], field: str) -> str:
    value = raw.get(field)
    if value is None:
        raise AgentTaskValidationError(f"缺少字段: {field}")
    text = str(value).strip()
    if not text:
        raise AgentTaskValidationError(f"字段 {field} 不能为空")
    return text


def _read_mapping(value: Any, field: str, task_id: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise AgentTaskValidationError(f"task_id={task_id} 字段 {field} 必须是对象")
    return dict(value)


def _read_string_list(value: Any, field: str, task_id: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if "," in text:
            items = [x.strip() for x in text.split(",")]
        else:
            items = [text]
    elif isinstance(value, list):
        items = [str(x).strip() for x in value]
    else:
        raise AgentTaskValidationError(f"task_id={task_id} 字段 {field} 必须是字符串或列表")

    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _parse_positive_int(value: Any, label: str, task_id: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentTaskValidationError(
            f"task_id={task_id} 字段 {label} 必须是正整数"
        ) from exc
    if parsed <= 0:
        raise AgentTaskValidationError(f"task_id={task_id} 字段 {label} 必须 > 0")
    return parsed


def _parse_horizons(raw: Any, default_horizon_hours: int, task_id: str) -> list[int]:
    if default_horizon_hours <= 0:
        raise AgentTaskValidationError("default_horizon_hours 必须 > 0")

    if raw is None:
        return [default_horizon_hours]
    if isinstance(raw, int):
        return [_parse_positive_int(raw, label="horizons", task_id=task_id)]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return [default_horizon_hours]
        parts = [x.strip() for x in text.split(",") if x.strip()]
        return _normalize_horizon_list(parts, task_id=task_id)
    if isinstance(raw, list):
        return _normalize_horizon_list(raw, task_id=task_id)
    raise AgentTaskValidationError(f"task_id={task_id} horizons 格式不合法")


def _normalize_horizon_list(items: list[Any], task_id: str) -> list[int]:
    out: list[int] = []
    for item in items:
        if isinstance(item, int):
            value = _parse_positive_int(item, label="horizon", task_id=task_id)
        else:
            text = str(item).strip().lower()
            matched = re.fullmatch(r"(\d+)\s*h?", text)
            if not matched:
                raise AgentTaskValidationError(
                    f"task_id={task_id} horizon 格式错误: {item}"
                )
            value = _parse_positive_int(
                matched.group(1), label="horizon", task_id=task_id
            )
        if value not in out:
            out.append(value)
    if not out:
        raise AgentTaskValidationError(f"task_id={task_id} horizons 不能为空")
    return out
