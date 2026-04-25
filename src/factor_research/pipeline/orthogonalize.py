"""Optional orthogonalization helpers for factors."""

from __future__ import annotations

import pandas as pd

from .neutralize import neutralize_ols


def orthogonalize_against_benchmarks(
    factor: pd.Series,
    benchmark_factors: pd.DataFrame,
    by: pd.Series | None = None,
    add_intercept: bool = True,
    min_obs: int | None = None,
) -> pd.Series:
    """Residualize factor against benchmark factors."""
    if benchmark_factors.empty:
        raise ValueError("benchmark_factors is empty.")
    return neutralize_ols(
        factor=factor,
        exposures=benchmark_factors.astype(float),
        categorical_cols=[],
        by=by,
        add_intercept=add_intercept,
        min_obs=min_obs,
    )


def maybe_orthogonalize(
    factor: pd.Series,
    benchmark_factors: pd.DataFrame | None,
    enabled: bool,
    by: pd.Series | None = None,
    add_intercept: bool = True,
    min_obs: int | None = None,
) -> pd.Series:
    """Orthogonalize when enabled, else return factor unchanged."""
    if not enabled:
        return factor
    if benchmark_factors is None:
        raise ValueError("benchmark_factors is required when orthogonalization is enabled.")
    return orthogonalize_against_benchmarks(
        factor=factor,
        benchmark_factors=benchmark_factors,
        by=by,
        add_intercept=add_intercept,
        min_obs=min_obs,
    )
