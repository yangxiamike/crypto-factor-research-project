"""V1 workflow adapter that bridges config profiles to pipeline execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import load_yaml_config
from .pipeline import run_factor_pipeline

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_CONFIG_PATH = ROOT / "configs" / "factor_test_profiles.yaml"


def _build_pipeline_profile(
    profile_name: str,
    profile_cfg: dict[str, Any],
) -> dict[str, Any]:
    exposure_cols = list(profile_cfg.get("neutralize_exposures", []))
    categorical_cols = ["primary_category"] if "primary_category" in exposure_cols else []
    group_col = profile_cfg.get("group_by") if profile_cfg.get("within_category") else None
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
    """Build per-profile working frame and effective date column."""
    if group_col is None:
        return frame, "date"

    if group_col not in frame.columns:
        raise KeyError(f"group_col '{group_col}' is not in input frame.")

    out = frame.copy()
    out["_group_date"] = (
        out["date"].astype("string") + "|" + out[group_col].astype("string").fillna("UNKNOWN")
    )
    return out, "_group_date"


def _mock_input_data(seed: int = 20260424) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    assets = [f"asset_{i:03d}" for i in range(1, 81)]
    categories = np.array(["L1", "L2", "DeFi", "Meme", "Infrastructure"])

    rows: list[dict[str, Any]] = []
    for date in dates:
        for asset in assets:
            beta = rng.normal(1.0, 0.25)
            size = rng.normal(0.0, 1.0)
            liquidity = rng.normal(0.0, 1.0)
            volatility = np.abs(rng.normal(0.0, 1.0))
            age = rng.integers(10, 1800)
            primary_category = rng.choice(categories)

            # Build signal with a controlled alpha component plus exposure noise.
            alpha_component = rng.normal(0.0, 0.015)
            raw_factor = (
                alpha_component
                + 0.2 * beta
                - 0.1 * liquidity
                + 0.05 * volatility
                + rng.normal(0.0, 0.2)
            )
            forward_return = 0.05 * alpha_component + rng.normal(0.0, 0.02)

            rows.append(
                {
                    "date": date,
                    "asset_id": asset,
                    "raw_factor": raw_factor,
                    "forward_return": forward_return,
                    "beta": beta,
                    "size": size,
                    "liquidity": liquidity,
                    "volatility": volatility,
                    "age": float(age),
                    "primary_category": str(primary_category),
                }
            )
    return pd.DataFrame(rows)


def run_v1_workflow(
    profile_config_path: str | Path = DEFAULT_PROFILE_CONFIG_PATH,
    data: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    raw_cfg = load_yaml_config(profile_config_path)
    profiles = raw_cfg.get("profiles", {})
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("profiles config is empty or invalid.")

    frame = _mock_input_data() if data is None else data.copy()
    outputs: dict[str, pd.DataFrame] = {}

    for profile_name, profile_cfg in profiles.items():
        if not isinstance(profile_cfg, dict):
            continue
        runtime_profile = _build_pipeline_profile(profile_name, profile_cfg)
        working_frame, date_col = _build_working_frame(frame, runtime_profile.get("group_col"))
        runtime_profile["date_col"] = date_col
        result = run_factor_pipeline(working_frame, runtime_profile)
        used_col = "final"

        out = frame[["date", "asset_id", "forward_return"]].copy()
        out["factor"] = result["frame"][used_col]
        outputs[profile_name] = out
    return outputs
