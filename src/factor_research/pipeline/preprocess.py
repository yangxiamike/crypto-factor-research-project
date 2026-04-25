"""Cross-sectional preprocessing utilities for factor values."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

StandardizeMethod = Literal["zscore", "rank", "none"]


def winsorize_mad(series: pd.Series, n_mad: float = 5.0) -> pd.Series:
    """Winsorize a series by median +/- n_mad * 1.4826 * MAD."""
    if n_mad <= 0:
        raise ValueError("n_mad must be > 0.")

    result = series.astype(float).copy()
    valid = result.dropna()
    if valid.empty:
        return result

    median = valid.median()
    mad = (valid - median).abs().median()
    if mad == 0 or np.isnan(mad):
        return result

    scale = 1.4826 * mad
    lower = median - n_mad * scale
    upper = median + n_mad * scale
    return result.clip(lower=lower, upper=upper)


def zscore_standardize(series: pd.Series, ddof: int = 0) -> pd.Series:
    """Z-score standardization with NaN-safe and zero-variance handling."""
    result = series.astype(float).copy()
    valid = result.dropna()
    if valid.empty:
        return result

    mean = valid.mean()
    std = valid.std(ddof=ddof)
    if std == 0 or np.isnan(std):
        result.loc[valid.index] = 0.0
        return result

    result.loc[valid.index] = (valid - mean) / std
    return result


def rank_standardize(series: pd.Series) -> pd.Series:
    """Rank normalization to [-0.5, 0.5], robust for outliers."""
    result = series.astype(float).copy()
    valid = result.dropna()
    if valid.empty:
        return result

    pct_rank = valid.rank(method="average", pct=True)
    result.loc[valid.index] = pct_rank - 0.5
    return result


def preprocess_factor(
    data: pd.DataFrame,
    factor_col: str,
    date_col: str | None = None,
    winsorize: bool = True,
    n_mad: float = 5.0,
    standardize: StandardizeMethod = "zscore",
) -> pd.Series:
    """Apply cross-sectional winsorization and standardization."""
    if factor_col not in data.columns:
        raise KeyError(f"factor_col '{factor_col}' not found in data.")
    if date_col is not None and date_col not in data.columns:
        raise KeyError(f"date_col '{date_col}' not found in data.")
    if standardize not in {"zscore", "rank", "none"}:
        raise ValueError("standardize must be one of: 'zscore', 'rank', 'none'.")

    factor = data[factor_col].astype(float)

    def _process_one_group(group: pd.Series) -> pd.Series:
        out = group
        if winsorize:
            out = winsorize_mad(out, n_mad=n_mad)
        if standardize == "zscore":
            out = zscore_standardize(out)
        elif standardize == "rank":
            out = rank_standardize(out)
        return out

    if date_col is None:
        return _process_one_group(factor)

    return factor.groupby(data[date_col], sort=False).transform(_process_one_group)
