from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROFILE_EXPOSURE_MAPPING: dict[str, tuple[str, ...]] = {
    "raw": (),
    "base_neutral": ("beta", "size", "liquidity"),
    "strict_neutral": (
        "beta",
        "size",
        "liquidity",
        "volatility",
        "age",
        "primary_category",
    ),
    "within_category": ("primary_category",),
}


DEFAULT_PROFILE_ORDER: tuple[str, ...] = (
    "raw",
    "base_neutral",
    "strict_neutral",
    "within_category",
)


def get_profile_exposures(profile_name: str) -> tuple[str, ...]:
    if profile_name not in PROFILE_EXPOSURE_MAPPING:
        raise KeyError(f"Unknown profile: {profile_name}")
    return PROFILE_EXPOSURE_MAPPING[profile_name]


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {config_path}")
    return data
