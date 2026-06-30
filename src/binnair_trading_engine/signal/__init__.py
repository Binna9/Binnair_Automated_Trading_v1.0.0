"""
시그널 정책 패키지 공개 API다.
ConsecutiveSignalPolicy를 외부 모듈에서 사용할 수 있게 노출한다.
"""

from binnair_trading_engine.signal.policy import ConsecutiveSignalPolicy

__all__ = ["ConsecutiveSignalPolicy"]
