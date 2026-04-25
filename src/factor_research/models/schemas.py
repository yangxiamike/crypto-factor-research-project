from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


TradableStatus = Literal[
    "active",
    "suspended",
    "delisted",
    "listing_pending",
    "maintenance",
    "unknown",
]

MarketType = Literal["spot", "perpetual"]
DecisionStatus = Literal["rejected", "watchlist", "research_pass"]


@dataclass
class AssetMetadata:
    asset_id: str
    symbol: str
    exchange_symbol: str
    coingecko_id: str
    market_type: MarketType
    exchange: str
    quote_asset: str
    listed_time: str
    delisted_time: str | None
    tradable_status: TradableStatus
    primary_category: str
    category_effective_time: str
    metadata_source: str
    metadata_version: str


@dataclass
class UniverseSnapshot:
    snapshot_time: str
    universe_name: str
    asset_id: str
    rank_metric: str
    rank_value: float
    rank_number: int
    is_member: bool
    exclude_reason: str | None
    config_version: str


@dataclass
class FactorExposures:
    exposure_time: str
    asset_id: str
    beta: float | None
    size: float | None
    liquidity: float | None
    volatility: float | None
    age: float | None
    primary_category: str
    calc_config_version: str


@dataclass
class FactorValues:
    factor_time: str
    asset_id: str
    factor_id: str
    factor_name: str
    raw_value: float | None
    winsorized_value: float | None
    zscore_value: float | None
    rank_value: float | None
    neutralized_value: float | None
    factor_version: str


@dataclass
class ForwardReturns:
    label_start_time: str
    label_end_time: str
    horizon: str
    asset_id: str
    gross_return: float | None
    net_return: float | None
    fee_cost: float | None
    slippage_cost: float | None
    funding_cost: float | None


@dataclass
class FactorEvaluation:
    factor_id: str
    profile_name: str
    universe_name: str
    horizon: str
    rank_ic_mean: float | None
    rank_ic_tstat: float | None
    ic_positive_ratio: float | None
    long_short_return: float | None
    turnover: float | None
    coverage_ratio: float | None
    cost_adjusted_return: float | None


@dataclass
class FactorDecision:
    decision_status: DecisionStatus
    alpha_type: str
    passed_profiles: list[str] = field(default_factory=list)
    failed_profiles: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    acceptance_rule_version: str = ""


SCHEMA_REGISTRY: dict[str, type[Any]] = {
    "asset_metadata": AssetMetadata,
    "universe_snapshot": UniverseSnapshot,
    "factor_exposures": FactorExposures,
    "factor_values": FactorValues,
    "forward_returns": ForwardReturns,
    "factor_evaluation": FactorEvaluation,
    "factor_decision": FactorDecision,
}


def schema_names() -> tuple[str, ...]:
    return tuple(SCHEMA_REGISTRY.keys())


def to_record(instance: Any) -> dict[str, Any]:
    return asdict(instance)
