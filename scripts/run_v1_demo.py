from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from factor_research.config import load_yaml_config
from factor_research.evaluation import (
    coverage_ratio,
    decide_profile,
    ic_positive_ratio,
    layered_long_short_return,
    rank_ic,
)
from factor_research.workflow import run_v1_workflow


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


def evaluate_profile(frame: pd.DataFrame) -> dict[str, float]:
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


def main() -> None:
    decision_config = _build_decision_config_from_yaml(
        ROOT / "configs" / "factor_acceptance.yaml"
    )
    workflow_output = run_v1_workflow()
    print("=== V1 Demo: Profile Evaluation ===")
    for profile, frame in workflow_output.items():
        metrics = evaluate_profile(frame)
        decision = decide_profile(metrics, config=decision_config)
        print(f"\n[Profile] {profile}")
        for metric_name, metric_value in metrics.items():
            print(f"  - {metric_name}: {metric_value:.6f}")
        print(f"  - decision: {decision.label}")
        if decision.reasons:
            print(f"  - reasons: {', '.join(decision.reasons)}")


if __name__ == "__main__":
    main()
