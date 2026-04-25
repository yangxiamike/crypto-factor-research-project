"""First-version factor pipeline workflow."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .neutralize import neutralize_ols
from .orthogonalize import maybe_orthogonalize
from .preprocess import preprocess_factor


def _require_columns(data: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in data.columns]
    if missing:
        raise KeyError(f"Missing {label} columns: {missing}")


def run_factor_pipeline(
    data: pd.DataFrame,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Run first-version factor workflow:
    validate -> preprocess -> neutralize -> optional orthogonalize.
    """
    if data.empty:
        raise ValueError("input data is empty.")

    factor_col = profile.get("factor_col")
    if not factor_col:
        raise ValueError("profile['factor_col'] is required.")

    date_col = profile.get("date_col")
    required = [factor_col] + ([date_col] if date_col else [])
    _require_columns(data, required, "base")

    preprocess_cfg = profile.get("preprocess", {})
    neutral_cfg = profile.get("neutralize", {})
    ortho_cfg = profile.get("orthogonalize", {})

    by = data[date_col] if date_col else None
    raw_factor = data[factor_col].astype(float)

    preprocessed = preprocess_factor(
        data=data,
        factor_col=factor_col,
        date_col=date_col,
        winsorize=preprocess_cfg.get("winsorize", True),
        n_mad=preprocess_cfg.get("n_mad", 5.0),
        standardize=preprocess_cfg.get("standardize", "zscore"),
    )

    neutral_enabled = neutral_cfg.get("enabled", False)
    neutralized = preprocessed
    if neutral_enabled:
        exposure_cols = neutral_cfg.get("exposure_cols", [])
        if not exposure_cols:
            raise ValueError("neutralize.enabled=True requires neutralize.exposure_cols.")
        _require_columns(data, exposure_cols, "exposure")
        neutralized = neutralize_ols(
            factor=preprocessed,
            exposures=data[exposure_cols],
            categorical_cols=neutral_cfg.get("categorical_cols", []),
            by=by,
            add_intercept=neutral_cfg.get("add_intercept", True),
            min_obs=neutral_cfg.get("min_obs"),
        )

    orth_enabled = ortho_cfg.get("enabled", False)
    benchmark_cols = ortho_cfg.get("benchmark_cols", [])
    benchmark_df = None
    if orth_enabled:
        if not benchmark_cols:
            raise ValueError("orthogonalize.enabled=True requires orthogonalize.benchmark_cols.")
        _require_columns(data, benchmark_cols, "benchmark")
        benchmark_df = data[benchmark_cols].astype(float)

    final_factor = maybe_orthogonalize(
        factor=neutralized,
        benchmark_factors=benchmark_df,
        enabled=orth_enabled,
        by=by,
        add_intercept=ortho_cfg.get("add_intercept", True),
        min_obs=ortho_cfg.get("min_obs"),
    )

    result_frame = pd.DataFrame(
        {
            "raw": raw_factor,
            "preprocessed": preprocessed,
            "neutralized": neutralized,
            "final": final_factor,
        },
        index=data.index,
    )

    diagnostics = {
        "n_rows": int(len(data)),
        "n_raw_non_na": int(raw_factor.notna().sum()),
        "n_preprocessed_non_na": int(preprocessed.notna().sum()),
        "n_neutralized_non_na": int(neutralized.notna().sum()),
        "n_final_non_na": int(final_factor.notna().sum()),
        "neutralize_enabled": bool(neutral_enabled),
        "orthogonalize_enabled": bool(orth_enabled),
    }

    return {
        "frame": result_frame,
        "series": {
            "raw": raw_factor,
            "preprocessed": preprocessed,
            "neutralized": neutralized,
            "final": final_factor,
        },
        "diagnostics": diagnostics,
    }
