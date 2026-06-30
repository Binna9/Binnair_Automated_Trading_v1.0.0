"""
자동매매 엔진의 핵심 도메인 객체를 정의한다.
시세, 예측, 시그널, 주문, 체결, 포지션, 실행 컨텍스트를 모듈 간 공통 언어로 사용한다.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    """시그널 도메인 모델."""

    symbol: str
    action: SignalAction
    confidence: float = 0.0
    price_hint: float | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    run_id: str = ""
    strategy_id: str = ""
    model_version: str = ""
    feature_set_version: str = ""


@dataclass
class Order:
    """주문 도메인 모델."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    order_id: str | None = None
    client_order_id: str | None = None
    signal_id: str | None = None
    run_id: str = ""
    correlation_id: str = ""
    reduce_only: bool = False
    close_position: bool = False
    position_side: str = "BOTH"  # BOTH | LONG | SHORT (Binance Futures)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Position:
    """
    포지션 도메인 모델.
    엔진이 참조하는 현재 보유 상태의 기준 객체.
    초기 버전: single symbol / single position.
    수량 0이면 CLOSED.
    """

    symbol: str
    quantity: float
    avg_entry_price: float
    side: str = "LONG"  # LONG | SHORT
    tp_price: float | None = None
    sl_price: float | None = None
    status: str = "OPEN"  # OPEN | CLOSED
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None
    updated_at: datetime = field(default_factory=datetime.utcnow)
    # 호환성 유지
    position_id: str = ""
    run_id: str = ""
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0  # 청산 시 (exit_price - avg_entry_price) * quantity (LONG)
    exit_reason: str = ""  # TAKE_PROFIT | STOP_LOSS (청산 시에만)
    exit_price: float = 0.0  # 청산가 (청산 시에만)

    def is_open(self) -> bool:
        """포지션이 보유 중인지. 수량 0이면 False."""
        return self.status == "OPEN" and self.quantity > 0

    def is_long(self) -> bool:
        """롱 포지션인지."""
        return self.side == "LONG"

    def is_closed(self) -> bool:
        """청산 완료 여부. 수량 0이면 CLOSED로 간주."""
        return self.status == "CLOSED" or self.quantity <= 0


@dataclass
class Trade:
    """체결 내역 도메인 모델."""

    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    run_id: str = ""
    correlation_id: str = ""
    executed_at: datetime = field(default_factory=datetime.utcnow)
    commission: float = 0.0


@dataclass
class OrderIntent:
    """주문 의도 (전략 → 거래소 전달용)."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    time_in_force: str = "GTC"
    reduce_only: bool = False
    position_side: str = "BOTH"  # BOTH | LONG | SHORT
    leverage: int | None = None


@dataclass
class Prediction:
    """
    예측 결과 (Predictor 출력).
    score/probability/signal 표준화. Java 웹포털 등 외부 연동용.
    """

    action: SignalAction
    confidence: float = 0.0
    price_hint: float | None = None
    score: float | None = None  # 표준화 스코어 (예: -1~1)
    probability: dict[str, float] | None = None  # {"BUY": x, "SELL": y, "HOLD": z}
    model_version: str = ""
    feature_set_version: str = ""
    scaler_version: str = ""


@dataclass
class TradeContext:
    """거래 컨텍스트 (BinnAIR 추적용)."""

    run_id: str
    strategy_id: str
    model_version: str
    feature_set_version: str
    symbol: str = ""

    @classmethod
    def from_signal(cls, signal: "Signal", engine_ctx: "EngineContext") -> "TradeContext":
        return cls(
            run_id=engine_ctx.run_id,
            strategy_id=engine_ctx.strategy_id,
            model_version=engine_ctx.model_version,
            feature_set_version=engine_ctx.feature_set_version,
            symbol=signal.symbol,
        )

    @classmethod
    def from_snapshot(
        cls, snapshot: "MarketSnapshot", engine_ctx: "EngineContext"
    ) -> "TradeContext":
        return cls(
            run_id=engine_ctx.run_id,
            strategy_id=engine_ctx.strategy_id,
            model_version=engine_ctx.model_version,
            feature_set_version=engine_ctx.feature_set_version,
            symbol=snapshot.symbol,
        )


@dataclass
class EngineContext:
    """엔진 실행 컨텍스트."""

    version: str
    run_id: str
    strategy_id: str
    model_version: str
    feature_set_version: str
    user_id: str = "default"  # 사용자별 이력 분리


@dataclass
class AuditLog:
    """감사 로그."""

    event: str
    run_id: str
    correlation_id: str = ""
    data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MarketSnapshot:
    """
    마켓 스냅샷 (polling tick / market event 입력).
    시세, 심볼, 타임스탬프 등 최소 정보.
    """

    symbol: str
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    run_id: str = ""
    correlation_id: str = ""


@dataclass
class OhlcvCandle:
    """거래소 OHLCV 캔들 데이터."""

    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None
    trade_count: int | None = None
