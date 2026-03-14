"""거래소 어댑터."""

from binnair_trading_engine.exchange.binance_spot import BinanceSpotAdapter
from binnair_trading_engine.exchange.interface import ExchangeAdapter
from binnair_trading_engine.exchange.paper import PaperExchangeAdapter

__all__ = [
    "ExchangeAdapter",
    "PaperExchangeAdapter",
    "BinanceSpotAdapter",
    "create_exchange",
]


def create_exchange(config) -> ExchangeAdapter:
    """설정에 따라 거래소 어댑터 생성. paper_mode=False 시 Binance Spot 실거래."""
    from binnair_trading_engine.config.settings import EngineConfig

    cfg: EngineConfig = config
    if cfg.exchange.paper_mode:
        return PaperExchangeAdapter()

    base_url = cfg.exchange.base_url or "https://api.binance.com"
    if not cfg.exchange.api_key or not cfg.exchange.api_secret:
        raise ValueError(
            "exchange.paper_mode=false 시 api_key, api_secret 필수. "
            "config.yaml의 exchange.api_key, exchange.api_secret 설정."
        )
    return BinanceSpotAdapter(
        api_key=cfg.exchange.api_key,
        api_secret=cfg.exchange.api_secret,
        base_url=base_url,
    )
