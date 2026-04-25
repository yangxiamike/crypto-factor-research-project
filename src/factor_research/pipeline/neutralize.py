"""OLS residual neutralization utilities."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def _is_categorical_dtype(series: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(series) or pd.api.types.is_categorical_dtype(
        series
    ) or pd.api.types.is_bool_dtype(series)


def _prepare_design_matrix(
    exposures: pd.DataFrame,
    categorical_cols: Sequence[str] | None = None,
    add_intercept: bool = True,
) -> pd.DataFrame:
    if exposures.empty:
        raise ValueError("exposures is empty.")

    cat_cols = set(categorical_cols or [])
    unknown_cats = cat_cols - set(exposures.columns)
    if unknown_cats:
        raise KeyError(f"categorical_cols not found in exposures: {sorted(unknown_cats)}")

    auto_cat_cols = [col for col in exposures.columns if _is_categorical_dtype(exposures[col])]
    cat_cols.update(auto_cat_cols)

    num_cols = [col for col in exposures.columns if col not in cat_cols]
    num_part = exposures[num_cols].astype(float) if num_cols else pd.DataFrame(index=exposures.index)

    cat_part = pd.DataFrame(index=exposures.index)
    if cat_cols:
        raw = exposures[list(cat_cols)].copy()
        for col in raw.columns:
            raw[col] = raw[col].astype("string").fillna("__MISSING__")
        cat_part = pd.get_dummies(raw, columns=raw.columns, drop_first=True, dtype=float)

    design = pd.concat([num_part, cat_part], axis=1)
    if design.empty:
        raise ValueError("No valid exposure columns after preprocessing.")

    if add_intercept:
        design.insert(0, "intercept", 1.0)

    return design


def _neutralize_one_group(
    y: pd.Series,
    design: pd.DataFrame,
    min_obs: int | None = None,
) -> pd.Series:
    residual = pd.Series(np.nan, index=y.index, dtype=float)

    valid_mask = y.notna() & design.notna().all(axis=1)
    if not valid_mask.any():
        return residual

    x = design.loc[valid_mask].to_numpy(dtype=float)
    yv = y.loc[valid_mask].to_numpy(dtype=float)

    effective_min_obs = min_obs if min_obs is not None else x.shape[1] + 1
    if len(yv) < effective_min_obs:
        return residual

    beta, _, rank, _ = np.linalg.lstsq(x, yv, rcond=None)
    if rank < x.shape[1]:
        return residual

    fitted = x @ beta
    residual.loc[valid_mask] = yv - fitted
    return residual


def neutralize_ols(
    factor: pd.Series,
    exposures: pd.DataFrame,
    categorical_cols: Sequence[str] | None = None,
    by: pd.Series | None = None,
    add_intercept: bool = True,
    min_obs: int | None = None,
) -> pd.Series:
    """Neutralize factor by OLS residualization against exposures."""
    if not factor.index.equals(exposures.index):
        raise ValueError("factor and exposures must share exactly the same index.")

    design = _prepare_design_matrix(
        exposures=exposures,
        categorical_cols=categorical_cols,
        add_intercept=add_intercept,
    )

    if by is None:
        return _neutralize_one_group(factor.astype(float), design, min_obs=min_obs)

    if not factor.index.equals(by.index):
        raise ValueError("when provided, 'by' must share the same index as factor.")

    out = pd.Series(np.nan, index=factor.index, dtype=float)
    for _, idx in by.groupby(by, sort=False).groups.items():
        grp_idx = pd.Index(idx)
        out.loc[grp_idx] = _neutralize_one_group(
            factor.loc[grp_idx].astype(float),
            design.loc[grp_idx],
            min_obs=min_obs,
        )
    return out
