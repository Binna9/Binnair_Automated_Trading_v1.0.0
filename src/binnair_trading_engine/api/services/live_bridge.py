"""
Binance Futures User Data Stream + Mark Price → LiveAccountHub 브리지.

config.exchange.base_url 로 testnet/mainnet 자동 전환.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from binnair_trading_engine.api.services.live_hub import LiveAccountHub
from binnair_trading_engine.api.services.wallet_service import fetch_wallet_info
from binnair_trading_engine.config.settings import EngineConfig
from binnair_trading_engine.exchange.binance_endpoints import (
    exchange_environment_label,
    futures_mark_price_stream_url,
    futures_stream_ws_base,
    futures_user_stream_url,
)
from binnair_trading_engine.exchange.binance_listen_key import BinanceListenKeyClient
from binnair_trading_engine.exchange.binance_stream_parser import (
    build_snapshot_from_wallet_api,
    parse_mark_price_event,
    parse_user_stream_event,
)

logger = logging.getLogger(__name__)


class BinanceLiveBridge:

    def __init__(self, config: EngineConfig, hub: LiveAccountHub) -> None:
        self._config = config
        self._hub = hub
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._listen_key: str | None = None
        self._listen_client: BinanceListenKeyClient | None = None

    async def refresh_snapshot(self) -> None:
        """REST 스냅샷 재조회 (클라이언트 refresh 요청용)."""
        await self._refresh_snapshot()

    async def run(self) -> None:
        cfg = self._config
        live = cfg.api.live_stream
        if not live.enabled:
            await self._hub.set_stream_status(enabled=False, last_error=None)
            return

        if cfg.exchange.paper_mode:
            await self._run_paper_poll()
            return

        if cfg.exchange.market_type != "futures":
            await self._hub.set_stream_status(
                enabled=False,
                last_error=f"live stream supports futures only (got {cfg.exchange.market_type})",
            )
            return

        await self._refresh_snapshot()
        self._tasks = [
            asyncio.create_task(self._user_stream_loop(), name="binance-user-stream"),
        ]
        if live.mark_price_enabled:
            self._tasks.append(
                asyncio.create_task(self._mark_price_loop(), name="binance-mark-price")
            )
        self._tasks.append(
            asyncio.create_task(self._listen_key_keepalive_loop(), name="listen-key-keepalive")
        )
        await self._stop.wait()
        await self._shutdown()

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._shutdown()

    async def _shutdown(self) -> None:
        if self._listen_client and self._listen_key:
            await asyncio.to_thread(self._listen_client.close, self._listen_key)
        self._listen_key = None

    async def _refresh_snapshot(self) -> None:
        wallet = await asyncio.to_thread(fetch_wallet_info, self._config)
        wallet["environment"] = exchange_environment_label(
            self._config.exchange.base_url,
            self._config.exchange.paper_mode,
        )
        wallet["stream"] = {
            "ws_base": futures_stream_ws_base(self._config.exchange.base_url),
            "user_stream_enabled": self._config.api.live_stream.enabled,
            "mark_price_enabled": self._config.api.live_stream.mark_price_enabled,
            "symbol": self._config.market_data.symbol,
        }
        snapshot = build_snapshot_from_wallet_api(
            wallet,
            quote_asset=self._config.sizing.quote_asset,
            symbol=self._config.market_data.symbol,
        )
        await self._hub.set_snapshot(snapshot)
        await self._hub.broadcast(snapshot)

    async def _run_paper_poll(self) -> None:
        live = self._config.api.live_stream
        delay = max(2.0, live.reconnect_delay_seconds)
        await self._hub.set_stream_status(
            enabled=True,
            user_stream_connected=False,
            mark_price_connected=False,
            mode="paper_poll",
        )
        while not self._stop.is_set():
            try:
                await self._refresh_snapshot()
            except Exception as e:
                logger.warning("paper wallet poll failed: %s", e)
                await self._hub.set_stream_status(last_error=str(e))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def _listen_key_keepalive_loop(self) -> None:
        live = self._config.api.live_stream
        interval = max(60, live.listen_key_keepalive_seconds)
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass
            if not self._listen_client or not self._listen_key:
                continue
            try:
                await asyncio.to_thread(self._listen_client.keepalive, self._listen_key)
                logger.debug("listenKey keepalive ok")
            except Exception as e:
                logger.warning("listenKey keepalive failed: %s", e)
                await self._hub.set_stream_status(last_error=str(e))

    async def _ensure_listen_key(self) -> str:
        exc = self._config.exchange
        if self._listen_client is None:
            self._listen_client = BinanceListenKeyClient(
                api_key=exc.api_key,
                base_url=exc.base_url,
            )
        if not self._listen_key:
            self._listen_key = await asyncio.to_thread(self._listen_client.create)
        return self._listen_key

    async def _user_stream_loop(self) -> None:
        live = self._config.api.live_stream
        delay = max(1.0, live.reconnect_delay_seconds)
        while not self._stop.is_set():
            try:
                listen_key = await self._ensure_listen_key()
                url = futures_user_stream_url(self._config.exchange.base_url, listen_key)
                await self._hub.set_stream_status(
                    user_stream_connected=False,
                    user_stream_url=url.split("/ws/")[0] + "/ws/{listenKey}",
                    last_error=None,
                )
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=30) as ws:
                        await self._hub.set_stream_status(user_stream_connected=True)
                        logger.info("Binance user stream connected")
                        async for msg in ws:
                            if self._stop.is_set():
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_user_message(msg.data)
                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("user stream disconnected: %s", e)
                await self._hub.set_stream_status(
                    user_stream_connected=False,
                    last_error=str(e),
                )
                self._listen_key = None
            if not self._stop.is_set():
                await asyncio.sleep(delay)

    async def _mark_price_loop(self) -> None:
        live = self._config.api.live_stream
        delay = max(1.0, live.reconnect_delay_seconds)
        symbol = self._config.market_data.symbol
        url = futures_mark_price_stream_url(self._config.exchange.base_url, symbol)
        while not self._stop.is_set():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=30) as ws:
                        await self._hub.set_stream_status(mark_price_connected=True)
                        logger.info("Binance mark price stream connected: %s", symbol)
                        async for msg in ws:
                            if self._stop.is_set():
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_mark_price(msg.data)
                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("mark price stream disconnected: %s", e)
                await self._hub.set_stream_status(
                    mark_price_connected=False,
                    last_error=str(e),
                )
            if not self._stop.is_set():
                await asyncio.sleep(delay)

    async def _handle_user_message(self, raw_text: str) -> None:
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError:
            return
        for message in parse_user_stream_event(raw):
            if (
                message.get("type") == "stream_error"
                and message.get("code") == "listen_key_expired"
            ):
                self._listen_key = None
            await self._hub.apply_message(message)

    async def _handle_mark_price(self, raw_text: str) -> None:
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError:
            return
        message = parse_mark_price_event(raw)
        if message:
            await self._hub.apply_message(message)
