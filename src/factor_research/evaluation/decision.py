from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import math


DecisionLabel = str


@dataclass(frozen=True)
class DecisionResult:
    label: DecisionLabel
    reasons: list[str]


def _as_float(value: object) -> float:
    if value is None:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _meets_thresholds(
    metrics: Mapping[str, float], thresholds: Mapping[str, float]
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for metric_name, threshold in thresholds.items():
        current = _as_float(metrics.get(metric_name))
        target = _as_float(threshold)
        if math.isnan(current) or current < target:
            reasons.append(f"{metric_name}={current:.6f} < {target:.6f}")
    return len(reasons) == 0, reasons


def decide_profile(
    metrics: Mapping[str, float], config: Mapping[str, Mapping[str, float]]
) -> DecisionResult:
    """
    Rules:
    1) If any reject_if_below threshold is violated -> rejected
    2) Else if all pass_if_at_least thresholds are met -> research_pass
    3) Else if all watchlist_if_at_least thresholds are met -> watchlist
    4) Else -> rejected
    """
    reject_cfg = config.get("reject_if_below", {})
    pass_cfg = config.get("pass_if_at_least", {})
    watch_cfg = config.get("watchlist_if_at_least", {})

    reject_hit, reject_reasons = _meets_thresholds(metrics, reject_cfg)
    if not reject_hit:
        return DecisionResult(label="rejected", reasons=reject_reasons)

    pass_hit, pass_reasons = _meets_thresholds(metrics, pass_cfg)
    if pass_hit:
        return DecisionResult(label="research_pass", reasons=["met pass thresholds"])

    watch_hit, watch_reasons = _meets_thresholds(metrics, watch_cfg)
    if watch_hit:
        return DecisionResult(label="watchlist", reasons=["met watchlist thresholds"])

    reasons = list(dict.fromkeys(pass_reasons + watch_reasons))
    if not reasons:
        reasons = ["did not meet watchlist/pass thresholds"]
    return DecisionResult(label="rejected", reasons=reasons)


def decide_many(
    metrics_by_profile: Mapping[str, Mapping[str, float]],
    config: Mapping[str, Mapping[str, float]],
) -> dict[str, DecisionResult]:
    return {
        profile: decide_profile(metrics=metric_map, config=config)
        for profile, metric_map in metrics_by_profile.items()
    }
