"""
거래소 어댑터 공통 인터페이스를 정의한다.
주문 실행, 포지션 조회, 잔고 조회, 보호 주문 등록 계약을 제공한다.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from binnair_trading_engine.domain.models import Order, OrderType, Position, Trade

if TYPE_CHECKING:
    from binnair_trading_engine.domain.models import OrderIntent


class ExchangeAdapter(ABC):
    """거래소 연동용 어댑터 인터페이스 (Binance 기준 설계)."""

    @property
    def manages_exit_orders(self) -> bool:
        """
        거래소가 TP/SL 보호주문(OCO 유사)을 직접 관리하는지 여부.
        True면 엔진의 로컬 ExitManager 청산을 비활성화할 수 있다.
        """
        return False

    def submit_order(
        self, intent: "OrderIntent", execution_price: float | None = None
    ) -> Order | None:
        """주문 의도를 Order로 변환 후 실행. execution_price: 시장가 체결가."""
        price = execution_price if execution_price is not None else intent.price
        order = Order(
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            quantity=intent.quantity,
            price=price,
            stop_price=None,
            reduce_only=intent.reduce_only,
            position_side=intent.position_side,
        )
        return self.place_order(order)

    def get_available_balance(self, asset: str = "USDT") -> float:
        """
        주문 가능 잔고 조회.

        실거래/테스트넷 어댑터는 거래소의 available balance를 반환한다.
        미지원 어댑터는 0.0을 반환하여 sizing 단계에서 주문을 차단하게 한다.
        """
        return 0.0

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        """주문 실행."""
        ...

    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """주문 취소."""
        ...

    @abstractmethod
    def get_position(self, symbol: str) -> Position | None:
        """심볼 포지션 조회."""
        ...

    @abstractmethod
    def get_all_positions(self) -> list[Position]:
        """전체 포지션 조회."""
        ...

    @abstractmethod
    def get_order(self, symbol: str, order_id: str) -> Order | None:
        """주문 상태 조회."""
        ...

    @abstractmethod
    def get_recent_trades(self, symbol: str, limit: int = 10) -> list[Trade]:
        """최근 체결 내역 조회."""
        ...

    def place_exit_orders(
        self,
        symbol: str,
        position_side: str,
        quantity: float,
        take_profit_price: float | None,
        stop_loss_price: float | None,
    ) -> list[Order]:
        """
        진입 직후 보호성 청산 주문(TP/SL) 등록.
        기본 구현은 미지원([] 반환).
        """
        return []
