"""
거래소 어댑터 팩토리 패키지다.
설정에 따라 paper, Binance Spot, Binance Futures 어댑터를 생성한다.
"""

from binnair_trading_engine.exchange.binance_futures import BinanceFuturesAdapter
from binnair_trading_engine.exchange.binance_spot import BinanceSpotAdapter
from binnair_trading_engine.exchange.interface import ExchangeAdapter
from binnair_trading_engine.exchange.paper import PaperExchangeAdapter

__all__ = [
    "ExchangeAdapter",
    "PaperExchangeAdapter",
    "BinanceSpotAdapter",
    "BinanceFuturesAdapter",
    "create_exchange",
]


def create_exchange(config) -> ExchangeAdapter:
    """설정에 따라 거래소 어댑터 생성."""
    from binnair_trading_engine.config.settings import EngineConfig

    cfg: EngineConfig = config
    if cfg.exchange.paper_mode:
        return PaperExchangeAdapter()

    market_type = (cfg.exchange.market_type or "spot").lower()
    if market_type not in ("spot", "futures"):
        raise ValueError(f"unsupported exchange.market_type: {cfg.exchange.market_type}")

    default_base = "https://api.binance.com" if market_type == "spot" else "https://fapi.binance.com"
    base_url = cfg.exchange.base_url or default_base
    if not cfg.exchange.api_key or not cfg.exchange.api_secret:
        raise ValueError(
            "exchange.paper_mode=false 시 api_key, api_secret 필수. "
            ".env 의 BINNAIR_EXCHANGE_API_KEY, BINNAIR_EXCHANGE_API_SECRET 설정."
        )
    if market_type == "futures":
        return BinanceFuturesAdapter(
            api_key=cfg.exchange.api_key,
            api_secret=cfg.exchange.api_secret,
            base_url=base_url,
            leverage=cfg.exchange.leverage,
            margin_type=cfg.exchange.margin_type,
            position_side_mode=cfg.exchange.position_side_mode,
        )

    return BinanceSpotAdapter(
        api_key=cfg.exchange.api_key,
        api_secret=cfg.exchange.api_secret,
        base_url=base_url,
    )
