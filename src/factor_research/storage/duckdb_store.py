from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import site

import pandas as pd

site.addsitedir(site.getusersitepackages())
import duckdb


@dataclass
class DuckDBStore:
    db_path: str

    def __post_init__(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self.db_path)
        self.ensure_tables()

    def close(self) -> None:
        self._conn.close()

    def ensure_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_bars (
                symbol VARCHAR NOT NULL,
                bar_interval VARCHAR NOT NULL,
                open_time TIMESTAMP NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                close_time TIMESTAMP,
                quote_volume DOUBLE,
                trades BIGINT,
                taker_buy_base_volume DOUBLE,
                taker_buy_quote_volume DOUBLE,
                source VARCHAR NOT NULL,
                ingested_at TIMESTAMP NOT NULL,
                PRIMARY KEY (symbol, bar_interval, open_time)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS asset_metadata (
                symbol VARCHAR NOT NULL PRIMARY KEY,
                base_asset VARCHAR,
                quote_asset VARCHAR,
                status VARCHAR,
                is_spot_trading_allowed BOOLEAN,
                is_margin_trading_allowed BOOLEAN,
                source VARCHAR NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS universe_snapshot (
                snapshot_time TIMESTAMP NOT NULL,
                symbol VARCHAR NOT NULL,
                is_in_universe BOOLEAN NOT NULL,
                rank_by_quote_volume INTEGER,
                source VARCHAR NOT NULL,
                PRIMARY KEY (snapshot_time, symbol)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_factor_tasks (
                run_id VARCHAR,
                task_id VARCHAR,
                factor_name VARCHAR,
                hypothesis VARCHAR,
                required_fields_json VARCHAR,
                formula_draft VARCHAR,
                formula_key VARCHAR,
                formula_params_json VARCHAR,
                direction VARCHAR,
                horizons_json VARCHAR,
                neutralization_profile_json VARCHAR,
                risk_checks_json VARCHAR,
                acceptance_rule_version VARCHAR,
                input_status VARCHAR,
                status VARCHAR,
                execution_status VARCHAR,
                message VARCHAR,
                created_at TIMESTAMP
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_factor_experiments (
                run_id VARCHAR,
                task_id VARCHAR,
                factor_name VARCHAR,
                horizon_hours INTEGER,
                profile_name VARCHAR,
                status VARCHAR,
                decision VARCHAR,
                reasons_json VARCHAR,
                sample_rows BIGINT,
                n_dates INTEGER,
                n_assets INTEGER,
                error_message VARCHAR,
                created_at TIMESTAMP
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS factor_evaluation (
                run_id VARCHAR,
                task_id VARCHAR,
                factor_name VARCHAR,
                horizon_hours INTEGER,
                profile_name VARCHAR,
                rank_ic DOUBLE,
                ic_positive_ratio DOUBLE,
                coverage_ratio DOUBLE,
                long_short_return DOUBLE,
                status VARCHAR,
                evaluation_time TIMESTAMP,
                created_at TIMESTAMP
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS factor_decision (
                run_id VARCHAR,
                task_id VARCHAR,
                factor_name VARCHAR,
                horizon_hours INTEGER,
                profile_name VARCHAR,
                decision VARCHAR,
                reasons_json VARCHAR,
                acceptance_rule_version VARCHAR,
                status VARCHAR,
                decision_time TIMESTAMP,
                created_at TIMESTAMP
            )
            """
        )

    def upsert_market_bars(self, bars: pd.DataFrame) -> int:
        if bars.empty:
            return 0
        frame = bars.copy()
        frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True).dt.tz_convert(None)
        frame["close_time"] = pd.to_datetime(frame["close_time"], utc=True).dt.tz_convert(None)
        frame["ingested_at"] = pd.Timestamp.utcnow().tz_localize(None)
        frame["source"] = "binance_rest"

        self._conn.register("bars_df", frame)
        inserted = self._conn.execute(
            """
            SELECT COUNT(*)
            FROM bars_df d
            WHERE NOT EXISTS (
                SELECT 1
                FROM market_bars t
                WHERE t.symbol = d.symbol
                  AND t.bar_interval = d.bar_interval
                  AND t.open_time = d.open_time
            )
            """
        ).fetchone()[0]
        self._conn.execute(
            """
            INSERT INTO market_bars
            SELECT
                d.symbol,
                d.bar_interval,
                d.open_time,
                d.open,
                d.high,
                d.low,
                d.close,
                d.volume,
                d.close_time,
                d.quote_volume,
                d.trades,
                d.taker_buy_base_volume,
                d.taker_buy_quote_volume,
                d.source,
                d.ingested_at
            FROM bars_df d
            WHERE NOT EXISTS (
                SELECT 1
                FROM market_bars t
                WHERE t.symbol = d.symbol
                  AND t.bar_interval = d.bar_interval
                  AND t.open_time = d.open_time
            )
            """
        )
        self._conn.unregister("bars_df")
        return int(inserted)

    def upsert_asset_metadata(self, assets: pd.DataFrame) -> int:
        if assets.empty:
            return 0
        frame = assets.copy()
        frame["updated_at"] = pd.Timestamp.utcnow().tz_localize(None)
        frame["source"] = "binance_rest"

        self._conn.register("assets_df", frame)
        self._conn.execute(
            """
            INSERT INTO asset_metadata
            SELECT
                d.symbol,
                d.base_asset,
                d.quote_asset,
                d.status,
                d.is_spot_trading_allowed,
                d.is_margin_trading_allowed,
                d.source,
                d.updated_at
            FROM assets_df d
            ON CONFLICT(symbol) DO UPDATE SET
                base_asset = excluded.base_asset,
                quote_asset = excluded.quote_asset,
                status = excluded.status,
                is_spot_trading_allowed = excluded.is_spot_trading_allowed,
                is_margin_trading_allowed = excluded.is_margin_trading_allowed,
                source = excluded.source,
                updated_at = excluded.updated_at
            """
        )
        self._conn.unregister("assets_df")
        return int(len(frame))

    def upsert_universe_snapshot(self, snapshot: pd.DataFrame) -> int:
        if snapshot.empty:
            return 0
        frame = snapshot.copy()
        frame["snapshot_time"] = pd.to_datetime(frame["snapshot_time"], utc=True).dt.tz_convert(None)
        frame["source"] = "binance_rest"

        self._conn.register("snapshot_df", frame)
        inserted = self._conn.execute(
            """
            SELECT COUNT(*)
            FROM snapshot_df d
            WHERE NOT EXISTS (
                SELECT 1
                FROM universe_snapshot t
                WHERE t.snapshot_time = d.snapshot_time
                  AND t.symbol = d.symbol
            )
            """
        ).fetchone()[0]
        self._conn.execute(
            """
            INSERT INTO universe_snapshot
            SELECT
                d.snapshot_time,
                d.symbol,
                d.is_in_universe,
                d.rank_by_quote_volume,
                d.source
            FROM snapshot_df d
            WHERE NOT EXISTS (
                SELECT 1
                FROM universe_snapshot t
                WHERE t.snapshot_time = d.snapshot_time
                  AND t.symbol = d.symbol
            )
            """
        )
        self._conn.unregister("snapshot_df")
        return int(inserted)
