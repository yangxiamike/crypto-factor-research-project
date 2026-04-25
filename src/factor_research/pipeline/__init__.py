"""Core pipeline APIs for factor preprocessing and residualization."""

from .neutralize import neutralize_ols
from .orthogonalize import maybe_orthogonalize, orthogonalize_against_benchmarks
from .preprocess import (
    preprocess_factor,
    rank_standardize,
    winsorize_mad,
    zscore_standardize,
)
from .workflow import run_factor_pipeline

__all__ = [
    "winsorize_mad",
    "zscore_standardize",
    "rank_standardize",
    "preprocess_factor",
    "neutralize_ols",
    "orthogonalize_against_benchmarks",
    "maybe_orthogonalize",
    "run_factor_pipeline",
]
