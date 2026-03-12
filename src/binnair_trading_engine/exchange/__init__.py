"""거래소 어댑터."""

from binnair_trading_engine.exchange.interface import ExchangeAdapter
from binnair_trading_engine.exchange.paper import PaperExchangeAdapter

__all__ = [
    "ExchangeAdapter",
    "PaperExchangeAdapter",
    "create_exchange",
]


def create_exchange(config) -> ExchangeAdapter:
    """설정에 따라 거래소 어댑터 생성. paper_mode=True 기본."""
    from binnair_trading_engine.config.settings import EngineConfig
    cfg: EngineConfig = config
    if cfg.exchange.paper_mode:
        return PaperExchangeAdapter()
    # TODO: 실거래 Binance 어댑터
    return PaperExchangeAdapter()
