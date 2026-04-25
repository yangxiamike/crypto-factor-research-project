from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class FormulaExecutionError(ValueError):
    """Raised when formula cannot run on current data."""


def compute_raw_factor(
    frame: pd.DataFrame,
    formula_key: str,
    formula_params: dict[str, Any],
    direction: str,
    asset_col: str,
    close_col: str,
    volume_col: str | None,
) -> pd.Series:
    """Compute whitelisted formulas on data already sorted by asset and time."""
    window = int(formula_params.get("window", 24))
    if window <= 0:
        raise FormulaExecutionError("window 必须是正整数。")

    if formula_key == "close_momentum":
        out = _close_momentum(frame, asset_col=asset_col, close_col=close_col, window=window)
    elif formula_key == "volume_zscore":
        out = _volume_zscore(
            frame,
            asset_col=asset_col,
            volume_col=volume_col,
            window=window,
        )
    elif formula_key == "volatility":
        out = _rolling_volatility(
            frame,
            asset_col=asset_col,
            close_col=close_col,
            window=window,
        )
    else:
        raise FormulaExecutionError(f"不支持的 formula_key: {formula_key}")

    if direction == "negative":
        out = -out
    return out.replace([np.inf, -np.inf], np.nan)


def _close_momentum(
    frame: pd.DataFrame,
    asset_col: str,
    close_col: str,
    window: int,
) -> pd.Series:
    grouped = frame.groupby(asset_col, sort=False)[close_col]
    shifted = grouped.shift(window)
    return np.log(frame[close_col] / shifted)


def _volume_zscore(
    frame: pd.DataFrame,
    asset_col: str,
    volume_col: str | None,
    window: int,
) -> pd.Series:
    if volume_col is None or volume_col not in frame.columns:
        raise FormulaExecutionError("volume_zscore 需要 volume 或 quote_volume 字段。")
    volume = pd.to_numeric(frame[volume_col], errors="coerce")
    grouped = volume.groupby(frame[asset_col], sort=False)
    rolling_mean = grouped.transform(lambda x: x.rolling(window=window, min_periods=window).mean())
    rolling_std = grouped.transform(lambda x: x.rolling(window=window, min_periods=window).std())
    return (volume - rolling_mean) / rolling_std


def _rolling_volatility(
    frame: pd.DataFrame,
    asset_col: str,
    close_col: str,
    window: int,
) -> pd.Series:
    ret = frame.groupby(asset_col, sort=False)[close_col].pct_change()
    return ret.groupby(frame[asset_col], sort=False).transform(
        lambda x: x.rolling(window=window, min_periods=window).std()
    )
