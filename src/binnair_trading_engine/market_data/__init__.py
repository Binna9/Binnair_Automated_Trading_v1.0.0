"""시세 수신 모듈."""

from binnair_trading_engine.market_data.binance_rest import BinanceRestMarketData
from binnair_trading_engine.market_data.history import (
    OhlcvDbPriceHistoryProvider,
    PriceHistoryProvider,
    create_price_history_provider,
)
from binnair_trading_engine.market_data.interface import MarketDataProvider

__all__ = [
    "MarketDataProvider",
    "BinanceRestMarketData",
    "PriceHistoryProvider",
    "OhlcvDbPriceHistoryProvider",
    "create_market_data_provider",
    "create_price_history_provider",
]


def create_market_data_provider(
    provider_type: str = "binance_rest",
    base_url: str = "https://api.binance.com",
    timeout: float = 10.0,
) -> MarketDataProvider:
    """설정에 따라 시세 제공자 생성."""
    if provider_type == "binance_rest":
        return BinanceRestMarketData(base_url=base_url, timeout=timeout)
    return BinanceRestMarketData(base_url=base_url, timeout=timeout)
