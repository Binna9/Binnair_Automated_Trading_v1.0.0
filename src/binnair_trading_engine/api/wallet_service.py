"""
거래소(testnet) 지갑 조회 — 모니터 API read-only.

config.exchange 설정으로 Binance Futures/Spot 잔고·포지션을 조회한다.
"""
from __future__ import annotations

from typing import Any

from binnair_trading_engine.config.settings import EngineConfig
from binnair_trading_engine.exchange import create_exchange
from binnair_trading_engine.exchange.binance_futures import BinanceFuturesAdapter
from binnair_trading_engine.risk.sizing import PercentEquitySizingPolicy


def fetch_wallet_info(config: EngineConfig) -> dict[str, Any]:
    """엔진 config 기준 거래소 지갑 스냅샷 + sizing 진단."""
    exc_cfg = config.exchange
    quote = config.sizing.quote_asset.upper()
    out: dict[str, Any] = {
        "paper_mode": exc_cfg.paper_mode,
        "market_type": exc_cfg.market_type,
        "quote_asset": quote,
        "base_url": exc_cfg.base_url,
        "ok": False,
        "sizing_config": {
            "min_order_notional_usdt": config.sizing.min_order_notional_usdt,
            "fallback_equity_usdt": config.sizing.fallback_equity_usdt,
            "max_position_notional_pct": config.sizing.max_position_notional_pct,
            "risk_per_trade_pct": config.sizing.risk_per_trade_pct,
        },
        "engine_diagnostics": {},
    }

    if exc_cfg.paper_mode:
        from binnair_trading_engine.exchange.paper import PaperExchangeAdapter

        paper = PaperExchangeAdapter()
        bal = paper.get_available_balance(quote)
        out["ok"] = True
        out["message"] = "paper_mode: simulated wallet (no Binance API call)"
        out["engine_diagnostics"] = {
            "available_balance": bal,
            "effective_equity": bal,
            "can_create_order": bal > 0,
        }
        return out

    try:
        exchange = create_exchange(config)
    except Exception as e:
        out["error"] = {"type": "config_error", "message": str(e)}
        return out

    if isinstance(exchange, BinanceFuturesAdapter):
        snap = exchange.fetch_wallet_snapshot()
        out.update(snap)
        available = exchange.get_available_balance(quote)
        effective_equity = available if available > 0 else config.sizing.fallback_equity_usdt
        out["engine_diagnostics"] = _build_engine_diagnostics(
            config=config,
            available_balance=available,
            effective_equity=effective_equity,
            sample_price=_sample_price(config),
        )
        return out

    out["error"] = {
        "type": "unsupported",
        "message": f"wallet API not implemented for market_type={exc_cfg.market_type}",
    }
    return out


def _sample_price(config: EngineConfig) -> float:
    symbol = config.market_data.symbol.upper()
    if symbol.endswith("USDT") and len(symbol) > 4:
        return 1.0
    return 100.0


def _build_engine_diagnostics(
    *,
    config: EngineConfig,
    available_balance: float,
    effective_equity: float,
    sample_price: float,
) -> dict[str, Any]:
    sl_pct = config.trade_rules.sl_pct
    sl_price = sample_price * (1.0 - sl_pct) if sl_pct > 0 else None
    sizing = PercentEquitySizingPolicy(config.sizing)
    result = sizing.calculate(
        equity=effective_equity,
        entry_price=sample_price,
        stop_loss_price=sl_price,
    )
    min_notional = config.sizing.min_order_notional_usdt
    return {
        "available_balance": available_balance,
        "effective_equity": effective_equity,
        "equity_source": "exchange"
        if available_balance > 0
        else ("fallback" if config.sizing.fallback_equity_usdt > 0 else "none"),
        "sizing_result": {
            "quantity": result.quantity,
            "notional_usdt": result.notional,
            "reason": result.reason,
            "is_valid": result.is_valid,
        },
        "can_create_order": result.is_valid and result.notional >= min_notional,
        "sample_sizing_price": sample_price,
    }
