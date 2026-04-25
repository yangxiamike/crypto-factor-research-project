from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from factor_research.data import BinancePublicClient
from factor_research.storage import DuckDBStore


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Binance market data into DuckDB.")
    parser.add_argument("--db-path", required=True, help="DuckDB file path.")
    parser.add_argument(
        "--limit-symbols",
        type=int,
        default=20,
        help="Number of top USDT symbols to ingest.",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        default=None,
        help="Kline start time in ISO format, e.g. 2026-04-01T00:00:00Z.",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        default=None,
        help="Kline end time in ISO format, e.g. 2026-04-24T00:00:00Z.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.limit_symbols <= 0:
        raise ValueError("--limit-symbols must be > 0")

    start_time = _parse_iso_datetime(args.start_time)
    end_time = _parse_iso_datetime(args.end_time)
    if start_time and end_time and start_time >= end_time:
        raise ValueError("--start-time must be earlier than --end-time")

    if start_time is None and end_time is None:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)

    client = BinancePublicClient()
    store = DuckDBStore(db_path=args.db_path)

    try:
        symbols_df = client.fetch_usdt_pairs(limit=args.limit_symbols)
        if symbols_df.empty:
            print("No USDT symbols fetched from Binance, nothing to ingest.")
            return

        metadata_df = symbols_df[
            [
                "symbol",
                "base_asset",
                "quote_asset",
                "status",
                "is_spot_trading_allowed",
                "is_margin_trading_allowed",
            ]
        ].copy()
        touched_assets = store.upsert_asset_metadata(metadata_df)

        snapshot_time = end_time or datetime.now(timezone.utc)
        snapshot_df = pd.DataFrame(
            {
                "snapshot_time": [snapshot_time] * len(symbols_df),
                "symbol": symbols_df["symbol"].to_list(),
                "is_in_universe": [True] * len(symbols_df),
                "rank_by_quote_volume": list(range(1, len(symbols_df) + 1)),
            }
        )
        inserted_snapshot = store.upsert_universe_snapshot(snapshot_df)

        total_inserted_bars = 0
        for symbol in symbols_df["symbol"]:
            bars_df = client.fetch_klines_1h(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
            )
            inserted = store.upsert_market_bars(bars_df)
            total_inserted_bars += inserted
            print(
                f"[{symbol}] fetched={len(bars_df)} inserted={inserted}",
                flush=True,
            )

        print("\n=== Ingest Summary ===")
        print(f"assets_touched={touched_assets}")
        print(f"universe_snapshot_inserted={inserted_snapshot}")
        print(f"market_bars_inserted={total_inserted_bars}")
        print(f"db_path={args.db_path}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
