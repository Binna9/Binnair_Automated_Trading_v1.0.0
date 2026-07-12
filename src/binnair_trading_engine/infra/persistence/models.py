"""
SQLAlchemy ORM 테이블 모델을 정의한다.
OHLCV, 실행 이력, 시그널, 주문, 포지션, 추론 이벤트, 감사 로그 스키마를 관리한다.
"""
from __future__ import annotations

from datetime import date, datetime

from binnair_trading_engine.infra.timezone import now_kst
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "trade"
metadata = MetaData(schema=SCHEMA)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    metadata = metadata


# ---------------------------------------------------------------------------
# ohlcv_candle
# ---------------------------------------------------------------------------
class OhlcvCandleModel(Base):
    """
    OHLCV 캔들 원천 데이터.

    Binance 등 거래소 API에서 받은 1분봉/5분봉 캔들을 저장한다.
    TimesFM 입력은 우선 close 시계열을 사용하지만, 이후 거래량/고가/저가 기반
    필터나 백테스트 검증을 위해 OHLCV 전체를 보존한다.
    """

    __tablename__ = "ohlcv_candle"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="거래 심볼. 예: BTCUSDT")
    timeframe: Mapped[str] = mapped_column(String(16), index=True, comment="캔들 주기. 예: 1m, 5m")
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, comment="캔들 시작 시각")
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="캔들 종료 시각")
    open: Mapped[float] = mapped_column(Float, comment="시가")
    high: Mapped[float] = mapped_column(Float, comment="고가")
    low: Mapped[float] = mapped_column(Float, comment="저가")
    close: Mapped[float] = mapped_column(Float, comment="종가. TimesFM 기본 입력 후보")
    volume: Mapped[float] = mapped_column(Float, comment="기준 자산 거래량")
    quote_volume: Mapped[float | None] = mapped_column(Float, nullable=True, comment="호가/견적 자산 거래대금")
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="해당 캔들 내 체결 수")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "open_time", name="uq_ohlcv_candle_symbol_timeframe_open_time"),
        Index("ix_ohlcv_candle_symbol_timeframe_open_time", "symbol", "timeframe", "open_time"),
        {"comment": "OHLCV 캔들 원천 데이터. TimesFM close 히스토리 및 백테스트용"},
    )


# ---------------------------------------------------------------------------
# engine_run
# ---------------------------------------------------------------------------
class EngineRunModel(Base):
    """
    엔진 실행 이력. (BinnAIR pipeline_runs 유사)
    run_id 기준 실행 단위 추적.
    """

    __tablename__ = "engine_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    model_version: Mapped[str] = mapped_column(String(64), index=True, comment="모델 버전")
    feature_set_version: Mapped[str] = mapped_column(String(64), index=True, comment="피처 버전")
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", comment="엔진 버전")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래 여부")
    status: Mapped[str] = mapped_column(String(32), default="running", comment="running|paused|stopped|error")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="시작 시각")
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="종료 시각")
    config_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="설정 스냅샷")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, onupdate=now_kst, comment="수정")

    __table_args__ = ({"comment": "엔진 실행 이력. run_id 기준 실행 세션 추적"},)


# ---------------------------------------------------------------------------
# strategy_config_snapshot
# ---------------------------------------------------------------------------
class StrategyConfigSnapshotModel(Base):
    """
    전략 설정 스냅샷.
    실행 시점 전략 파라미터 보관 (replay/debug용).
    """

    __tablename__ = "strategy_config_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="스냅샷 시각")
    config_json: Mapped[dict] = mapped_column(JSONB, comment="설정 JSON")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = ({"comment": "실행 시점 전략 설정 스냅샷 (replay/debug)"},)


# ---------------------------------------------------------------------------
# engine_runtime_state — UI active config + trading on/off
# ---------------------------------------------------------------------------
class EngineRuntimeStateModel(Base):
    """
    사용자별 엔진 런타임 상태.
    UI에서 저장한 L1 설정과 trading_enabled 플래그.
    """

    __tablename__ = "engine_runtime_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="활성 run_id")
    strategy_id: Mapped[str] = mapped_column(String(128), comment="활성 strategy_id")
    config_json: Mapped[dict] = mapped_column(JSONB, comment="UI runtime flat config")
    config_version: Mapped[int] = mapped_column(Integer, default=1, comment="설정 버전 (증가)")
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True, comment="매매 tick 활성")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="갱신 시각")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = ({"comment": "UI 런타임 설정(L1) 및 trading on/off"},)


# ---------------------------------------------------------------------------
# engine_command — start/stop 명령 큐
# ---------------------------------------------------------------------------
class EngineCommandModel(Base):
    """엔진 프로세스가 poll 하는 start/stop 명령."""

    __tablename__ = "engine_command"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    action: Mapped[str] = mapped_column(String(16), index=True, comment="start|stop")
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="명령 시점 runtime config")
    config_version: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="연결된 config_version")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, comment="pending|done|failed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="실패 사유")
    correlation_id: Mapped[str] = mapped_column(String(64), default="", index=True, comment="추적 ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, index=True, comment="생성")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="처리 시각")

    __table_args__ = ({"comment": "UI start/stop 명령 큐"},)


# ---------------------------------------------------------------------------
# signal_event
# ---------------------------------------------------------------------------
class SignalEventModel(Base):
    """
    시그널 이벤트.
    Predictor/Strategy 출력 BUY|SELL|HOLD 기록.
    """

    __tablename__ = "signal_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="심볼")
    timeframe: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="타임프레임")
    model_version: Mapped[str] = mapped_column(String(64), index=True, comment="모델 버전")
    signal_action: Mapped[str] = mapped_column(String(16), comment="BUY|SELL|HOLD")
    confidence: Mapped[float] = mapped_column(Float, default=0.0, comment="신뢰도")
    price_hint: Mapped[float | None] = mapped_column(Float, nullable=True, comment="참고가")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="", comment="추적 ID")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="이벤트 시각")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = (
        Index("ix_signal_event_run_symbol_at", "run_id", "symbol", "event_at"),
        {"comment": "Predictor/Strategy BUY|SELL|HOLD 시그널 이벤트"},
    )


# ---------------------------------------------------------------------------
# order_request
# ---------------------------------------------------------------------------
class OrderRequestModel(Base):
    """
    주문 요청 (엔진 → 거래소 전달 직전).
    """

    __tablename__ = "order_request"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="심볼")
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="거래소 주문 ID")
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="클라이언트 주문 ID")
    side: Mapped[str] = mapped_column(String(16), comment="BUY|SELL")
    order_type: Mapped[str] = mapped_column(String(16), comment="MARKET|LIMIT")
    quantity: Mapped[float] = mapped_column(Float, comment="수량")
    price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="가격")
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="조건부 주문 trigger 가격")
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False, comment="포지션 축소 전용 주문")
    position_side: Mapped[str] = mapped_column(String(16), default="BOTH", comment="BOTH|LONG|SHORT")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="", comment="추적 ID")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="요청 시각")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = ({"comment": "엔진→거래소 주문 요청 (체결 직전)"},)


# ---------------------------------------------------------------------------
# order_execution
# ---------------------------------------------------------------------------
class OrderExecutionModel(Base):
    """
    주문 체결/실행 결과.
    raw_response: 거래소 응답 원문 저장.
    """

    __tablename__ = "order_execution"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    order_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_request.id"), nullable=True, index=True, comment="주문요청 FK"
    )
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="심볼")
    order_id: Mapped[str] = mapped_column(String(64), index=True, comment="거래소 주문 ID")
    status: Mapped[str] = mapped_column(String(32), comment="FILLED|CANCELLED|REJECTED")
    executed_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="체결가")
    executed_quantity: Mapped[float] = mapped_column(Float, comment="체결 수량")
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="조건부 주문 trigger 가격")
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False, comment="포지션 축소 전용 주문")
    position_side: Mapped[str] = mapped_column(String(16), default="BOTH", comment="BOTH|LONG|SHORT")
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="거래소 원문")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="체결 시각")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = ({"comment": "주문 체결 결과 및 거래소 응답 원문"},)


# ---------------------------------------------------------------------------
# position_snapshot
# ---------------------------------------------------------------------------
class PositionSnapshotModel(Base):
    """
    포지션 스냅샷.
    특정 시점 포지션 상태 (replay/debug). TP/SL, side 포함.
    """

    __tablename__ = "position_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="심볼")
    side: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="LONG|SHORT")
    quantity: Mapped[float] = mapped_column(Float, comment="수량")
    avg_entry_price: Mapped[float] = mapped_column(Float, comment="평균 진입가")
    tp_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="목표가")
    sl_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="손절가")
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="OPEN|CLOSED")
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0, comment="미실현 손익")
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True, comment="실현 손익")
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="TAKE_PROFIT|STOP_LOSS")
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="청산가")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="진입 시각")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="청산 시각")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="스냅샷 시각")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = (
        Index("ix_position_snapshot_run_symbol_at", "run_id", "symbol", "snapshot_at"),
        {"comment": "포지션 스냅샷. OPEN/CLOSED, TP/SL, 실현/미실현 PnL"},
    )


# ---------------------------------------------------------------------------
# trade_result
# ---------------------------------------------------------------------------
class TradeResultModel(Base):
    """
    청산 완료 거래 1건 = 1 row.
    승률·기간별 손익 집계의 원천 데이터.
    """

    __tablename__ = "trade_result"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    trade_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="거래 UUID")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="심볼")
    side: Mapped[str] = mapped_column(String(16), comment="LONG|SHORT")
    quantity: Mapped[float] = mapped_column(Float, comment="체결 수량")
    entry_price: Mapped[float] = mapped_column(Float, comment="진입가")
    exit_price: Mapped[float] = mapped_column(Float, comment="청산가")
    entry_notional_usdt: Mapped[float] = mapped_column(Float, comment="진입 명목 USDT")
    realized_pnl: Mapped[float] = mapped_column(Float, comment="실현 손익 USDT")
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0, comment="거래 수익률 %")
    is_win: Mapped[bool] = mapped_column(Boolean, default=False, index=True, comment="승리 여부")
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="청산 사유")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="", comment="추적 ID")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="진입 시각")
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, comment="청산 시각")
    hold_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="보유 시간(초)")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    position_snapshot_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, unique=True, comment="position_snapshot FK"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = (
        Index("ix_trade_result_user_run_closed", "user_id", "run_id", "closed_at"),
        {"comment": "청산 완료 거래 결과. 승률·PnL 집계 원천"},
    )


# ---------------------------------------------------------------------------
# performance_daily
# ---------------------------------------------------------------------------
class PerformanceDailyModel(Base):
    """
    run_id + UTC 일별 성과 롤업.
    trade_result 청산 시 upsert.
    """

    __tablename__ = "performance_daily"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    period_date: Mapped[date] = mapped_column(Date, index=True, comment="UTC 기준 일자")
    trade_count: Mapped[int] = mapped_column(Integer, default=0, comment="거래 수")
    win_count: Mapped[int] = mapped_column(Integer, default=0, comment="승")
    loss_count: Mapped[int] = mapped_column(Integer, default=0, comment="패")
    breakeven_count: Mapped[int] = mapped_column(Integer, default=0, comment="무승부")
    realized_pnl_sum: Mapped[float] = mapped_column(Float, default=0.0, comment="일 실현손익 합")
    gross_profit: Mapped[float] = mapped_column(Float, default=0.0, comment="이익 거래 합")
    gross_loss: Mapped[float] = mapped_column(Float, default=0.0, comment="손실 거래 절대값 합")
    avg_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0, comment="평균 거래 수익률 %")
    opening_equity_usdt: Mapped[float | None] = mapped_column(Float, nullable=True, comment="일 시작 잔고")
    closing_equity_usdt: Mapped[float | None] = mapped_column(Float, nullable=True, comment="일 종료 잔고")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, onupdate=now_kst, comment="수정"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = (
        UniqueConstraint("user_id", "run_id", "period_date", name="uq_performance_daily_user_run_date"),
        {"comment": "일별 성과 롤업 (승률·PnL·수익률 계산용)"},
    )


# ---------------------------------------------------------------------------
# equity_snapshot
# ---------------------------------------------------------------------------
class EquitySnapshotModel(Base):
    """
    잔고 스냅샷. 엔진 시작·청산 시 기록.
    기간 수익률(%) 분모(기준 자본)로 사용.
    """

    __tablename__ = "equity_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, comment="스냅샷 시각")
    snapshot_date: Mapped[date] = mapped_column(Date, index=True, comment="UTC 일자")
    equity_usdt: Mapped[float] = mapped_column(Float, comment="지갑 USDT 잔고")
    cumulative_realized_pnl: Mapped[float] = mapped_column(Float, default=0.0, comment="누적 실현손익")
    source: Mapped[str] = mapped_column(String(32), default="engine_start", comment="engine_start|trade_close")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = (
        Index("ix_equity_snapshot_user_run_date", "user_id", "run_id", "snapshot_date"),
        {"comment": "잔고 스냅샷. 기간 수익률 분모 계산용"},
    )


# ---------------------------------------------------------------------------
# risk_event
# ---------------------------------------------------------------------------
class RiskEventModel(Base):
    """
    리스크 이벤트 (거부, 경고 등).
    """

    __tablename__ = "risk_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="심볼")
    event_type: Mapped[str] = mapped_column(String(64), comment="risk_rejected 등")
    reason: Mapped[str] = mapped_column(Text, comment="사유")
    intent_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="의도 데이터")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="이벤트 시각")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = ({"comment": "리스크 거부/경고 이벤트"},)


# ---------------------------------------------------------------------------
# model_inference_event
# ---------------------------------------------------------------------------
class ModelInferenceEventModel(Base):
    """
    모델 추론 이벤트.
    input_snapshot, output_prediction 저장 (replay/debug).
    """

    __tablename__ = "model_inference_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    strategy_id: Mapped[str] = mapped_column(String(128), index=True, comment="전략 ID")
    symbol: Mapped[str] = mapped_column(String(32), index=True, comment="심볼")
    model_version: Mapped[str] = mapped_column(String(64), index=True, comment="모델 버전")
    feature_set_version: Mapped[str] = mapped_column(String(64), index=True, comment="피처 버전")
    input_snapshot: Mapped[dict] = mapped_column(JSONB, comment="입력 MarketSnapshot")
    output_prediction: Mapped[dict] = mapped_column(JSONB, comment="출력 Prediction")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    inference_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="추론 시각")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = ({"comment": "모델 추론 I/O. TimesFM input_snapshot/output_prediction"},)


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------
class AuditLogModel(Base):
    """
    감사 로그.
    모든 주요 이벤트의 최종 기록.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="PK")
    user_id: Mapped[str] = mapped_column(String(36), index=True, default="default", comment="사용자 ID")
    run_id: Mapped[str] = mapped_column(String(128), index=True, comment="실행 ID")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="", comment="추적 ID")
    event: Mapped[str] = mapped_column(String(64), index=True, comment="이벤트명")
    data: Mapped[dict] = mapped_column(JSONB, default=dict, comment="추가 데이터")
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="종이거래")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst, comment="생성")

    __table_args__ = ({"comment": "주요 이벤트 감사 로그 (리스크 거부 등)"},)
