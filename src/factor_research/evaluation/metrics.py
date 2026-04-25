from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _to_series(values: Any, name: str) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.rename(name)
    return pd.Series(values, name=name)


def rank_ic(factor: Any, forward_return: Any) -> float:
    """Spearman-like rank IC between factor and forward return."""
    factor_s = _to_series(factor, "factor")
    ret_s = _to_series(forward_return, "forward_return")
    df = pd.concat([factor_s, ret_s], axis=1).dropna()
    if len(df) < 2:
        return float("nan")
    factor_rank = df["factor"].rank(method="average")
    ret_rank = df["forward_return"].rank(method="average")
    return float(factor_rank.corr(ret_rank))


def ic_positive_ratio(ic_values: Any, min_count: int = 1) -> float:
    """Ratio of positive IC observations."""
    ic_s = _to_series(ic_values, "ic").dropna()
    if len(ic_s) < max(1, min_count):
        return float("nan")
    return float((ic_s > 0).mean())


def coverage_ratio(values: Any, total_count: int | None = None) -> float:
    """Non-null ratio for a factor series."""
    s = _to_series(values, "values")
    total = len(s) if total_count is None else int(total_count)
    if total <= 0:
        return float("nan")
    return float(s.notna().sum() / total)


def layered_long_short_return(
    data: pd.DataFrame,
    factor_col: str = "factor",
    return_col: str = "forward_return",
    date_col: str = "date",
    n_layers: int = 5,
    min_universe: int | None = None,
) -> dict[str, float]:
    """
    Simple cross-sectional layered long-short return:
    by each date, long = top layer mean return, short = bottom layer mean return.
    """
    required_cols = {factor_col, return_col, date_col}
    missing = required_cols.difference(data.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if n_layers < 2:
        raise ValueError("n_layers must be >= 2")

    frame = data[[date_col, factor_col, return_col]].dropna().copy()
    if frame.empty:
        return {
            "period_count": 0.0,
            "long_return": float("nan"),
            "short_return": float("nan"),
            "long_short_return": float("nan"),
        }

    min_required = n_layers if min_universe is None else max(n_layers, min_universe)
    spreads: list[float] = []
    longs: list[float] = []
    shorts: list[float] = []

    for _, cross in frame.groupby(date_col, sort=True):
        if len(cross) < min_required:
            continue
        rank_pct = cross[factor_col].rank(method="first", pct=True)
        layer = np.ceil(rank_pct * n_layers).clip(1, n_layers).astype(int)
        cross = cross.assign(_layer=layer)

        long_ret = cross.loc[cross["_layer"] == n_layers, return_col].mean()
        short_ret = cross.loc[cross["_layer"] == 1, return_col].mean()
        if pd.isna(long_ret) or pd.isna(short_ret):
            continue
        longs.append(float(long_ret))
        shorts.append(float(short_ret))
        spreads.append(float(long_ret - short_ret))

    if not spreads:
        return {
            "period_count": 0.0,
            "long_return": float("nan"),
            "short_return": float("nan"),
            "long_short_return": float("nan"),
        }

    return {
        "period_count": float(len(spreads)),
        "long_return": float(np.mean(longs)),
        "short_return": float(np.mean(shorts)),
        "long_short_return": float(np.mean(spreads)),
    }
