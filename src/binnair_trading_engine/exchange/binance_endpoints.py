"""
Binance REST base_url → WebSocket stream URL 매핑.

testnet / mainnet 전환은 config.exchange.base_url 만 바꾸면 된다.
"""

from __future__ import annotations

# USD-M Futures
FUTURES_REST_TESTNET = "https://testnet.binancefuture.com"
FUTURES_REST_MAINNET = "https://fapi.binance.com"
FUTURES_WS_TESTNET = "wss://fstream.binancefuture.com"
FUTURES_WS_MAINNET = "wss://fstream.binance.com"


def normalize_rest_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def is_futures_testnet(rest_base_url: str) -> bool:
    host = normalize_rest_base_url(rest_base_url).lower()
    return "testnet" in host


def futures_stream_ws_base(rest_base_url: str) -> str:
    """User Data Stream / mark price 공용 fstream 베이스 URL."""
    if is_futures_testnet(rest_base_url):
        return FUTURES_WS_TESTNET
    return FUTURES_WS_MAINNET


def futures_user_stream_url(rest_base_url: str, listen_key: str) -> str:
    base = futures_stream_ws_base(rest_base_url)
    return f"{base}/ws/{listen_key}"


def futures_mark_price_stream_url(rest_base_url: str, symbol: str, interval: str = "1s") -> str:
    """단일 심볼 mark price (@1s 권장 — 미실현 PnL 갱신용)."""
    base = futures_stream_ws_base(rest_base_url)
    sym = symbol.upper()
    return f"{base}/ws/{sym.lower()}@markPrice@{interval}"


def exchange_environment_label(rest_base_url: str, paper_mode: bool) -> str:
    if paper_mode:
        return "paper"
    if is_futures_testnet(rest_base_url):
        return "futures_testnet"
    return "futures_mainnet"
