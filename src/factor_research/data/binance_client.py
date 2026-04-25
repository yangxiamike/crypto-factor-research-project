from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BASE_URL = "https://api.binance.com"
DEFAULT_COINBASE_BASE_URL = "https://api.exchange.coinbase.com"
DEFAULT_TIMEOUT_SECONDS = 15
MAX_KLINE_LIMIT = 1000


def _to_millis(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


@dataclass(frozen=True)
class BinancePublicClient:
    base_url: str = DEFAULT_BASE_URL
    coinbase_base_url: str = DEFAULT_COINBASE_BASE_URL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def _get(self, path: str, params: dict[str, Any] | None = None, use_coinbase: bool = False) -> Any:
        query = ""
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            query = "?" + urlencode(clean)
        base_url = self.coinbase_base_url if use_coinbase else self.base_url
        url = f"{base_url}{path}{query}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_coinbase_usd_pairs(self, limit: int) -> pd.DataFrame:
        products = self._get("/products", use_coinbase=True)
        rows: list[dict[str, Any]] = []
        for item in products:
            quote = item.get("quote_currency")
            if quote not in {"USD", "USDT"}:
                continue
            if item.get("status") not in {"online", "trading_disabled"}:
                continue
            product_id = item.get("id")
            base_asset = item.get("base_currency")
            if not product_id or not base_asset:
                continue
            rows.append(
                {
                    "symbol": product_id,
                    "base_asset": base_asset,
                    "quote_asset": quote,
                    "status": "TRADING" if item.get("trading_disabled") is False else "HALT",
                    "is_spot_trading_allowed": bool(not item.get("trading_disabled", False)),
                    "is_margin_trading_allowed": False,
                    "quote_volume_24h": 0.0,
                }
            )
        if not rows:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "base_asset",
                    "quote_asset",
                    "status",
                    "is_spot_trading_allowed",
                    "is_margin_trading_allowed",
                    "quote_volume_24h",
                ]
            )
        frame = pd.DataFrame(rows).sort_values(["quote_asset", "symbol"], ascending=[True, True])
        return frame.head(limit).reset_index(drop=True)

    def fetch_usdt_pairs(self, limit: int = 100) -> pd.DataFrame:
        if limit <= 0:
            raise ValueError("limit must be > 0")
        try:
            exchange_info = self._get("/api/v3/exchangeInfo")
            ticker_24h = self._get("/api/v3/ticker/24hr")
            ticker_map = {item["symbol"]: item for item in ticker_24h}

            rows: list[dict[str, Any]] = []
            for item in exchange_info.get("symbols", []):
                if item.get("quoteAsset") != "USDT":
                    continue
                if item.get("status") != "TRADING":
                    continue
                symbol = item["symbol"]
                ticker = ticker_map.get(symbol, {})
                quote_volume = float(ticker.get("quoteVolume", 0.0))
                rows.append(
                    {
                        "symbol": symbol,
                        "base_asset": item.get("baseAsset"),
                        "quote_asset": item.get("quoteAsset"),
                        "status": item.get("status"),
                        "is_spot_trading_allowed": bool(item.get("isSpotTradingAllowed", False)),
                        "is_margin_trading_allowed": bool(item.get("isMarginTradingAllowed", False)),
                        "quote_volume_24h": quote_volume,
                    }
                )

            if not rows:
                return self._fetch_coinbase_usd_pairs(limit=limit)
            frame = pd.DataFrame(rows).sort_values("quote_volume_24h", ascending=False)
            return frame.head(limit).reset_index(drop=True)
        except HTTPError:
            return self._fetch_coinbase_usd_pairs(limit=limit)

    def fetch_klines_1h(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        if not symbol:
            raise ValueError("symbol must not be empty")

        try:
            start_ms = _to_millis(start_time)
            end_ms = _to_millis(end_time)
            rows: list[list[Any]] = []

            next_start_ms = start_ms
            while True:
                payload = self._get(
                    "/api/v3/klines",
                    {
                        "symbol": symbol,
                        "interval": "1h",
                        "startTime": next_start_ms,
                        "endTime": end_ms,
                        "limit": MAX_KLINE_LIMIT,
                    },
                )
                if not payload:
                    break

                rows.extend(payload)
                if len(payload) < MAX_KLINE_LIMIT:
                    break

                last_open_time_ms = int(payload[-1][0])
                next_start_ms = last_open_time_ms + 1
                if end_ms is not None and next_start_ms > end_ms:
                    break

            data = pd.DataFrame(
                rows,
                columns=[
                    "open_time_ms",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time_ms",
                    "quote_volume",
                    "trades",
                    "taker_buy_base_volume",
                    "taker_buy_quote_volume",
                    "ignore",
                ],
            )
        except HTTPError:
            start_iso = start_time.isoformat() if start_time else None
            end_iso = end_time.isoformat() if end_time else None
            payload = self._get(
                f"/products/{symbol}/candles",
                {
                    "granularity": 3600,
                    "start": start_iso,
                    "end": end_iso,
                },
                use_coinbase=True,
            )
            if not payload:
                return pd.DataFrame(
                    columns=[
                        "symbol",
                        "bar_interval",
                        "open_time",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "close_time",
                        "quote_volume",
                        "trades",
                        "taker_buy_base_volume",
                        "taker_buy_quote_volume",
                    ]
                )
            coin = pd.DataFrame(
                payload,
                columns=["open_time_s", "low", "high", "open", "close", "volume"],
            )
            coin["open_time"] = pd.to_datetime(coin["open_time_s"], unit="s", utc=True)
            coin["close_time"] = coin["open_time"] + pd.Timedelta(hours=1)
            for col in ["open", "high", "low", "close", "volume"]:
                coin[col] = pd.to_numeric(coin[col], errors="coerce")
            coin["quote_volume"] = coin["volume"] * coin["close"]
            coin["trades"] = pd.Series([pd.NA] * len(coin), dtype="Int64")
            coin["taker_buy_base_volume"] = pd.NA
            coin["taker_buy_quote_volume"] = pd.NA
            coin["symbol"] = symbol
            coin["bar_interval"] = "1h"
            return coin[
                [
                    "symbol",
                    "bar_interval",
                    "open_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_volume",
                    "trades",
                    "taker_buy_base_volume",
                    "taker_buy_quote_volume",
                ]
            ].sort_values("open_time", ascending=True, kind="stable")

        if data.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "bar_interval",
                    "open_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_volume",
                    "trades",
                    "taker_buy_base_volume",
                    "taker_buy_quote_volume",
                ]
            )
        for col in [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ]:
            data[col] = pd.to_numeric(data[col], errors="coerce")
        data["trades"] = pd.to_numeric(data["trades"], errors="coerce").astype("Int64")
        data["open_time"] = pd.to_datetime(data["open_time_ms"], unit="ms", utc=True)
        data["close_time"] = pd.to_datetime(data["close_time_ms"], unit="ms", utc=True)
        data["symbol"] = symbol
        data["bar_interval"] = "1h"
        return data[
            [
                "symbol",
                "bar_interval",
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
            ]
        ].sort_values("open_time", ascending=True, kind="stable")
