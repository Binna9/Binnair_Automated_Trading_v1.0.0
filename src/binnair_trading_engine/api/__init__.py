"""
조회 API 패키지.

매매 엔진과 분리된 read-only FastAPI 레이어.
DB에 쌓인 포지션·시그널·주문 이력을 HTTP로 조회한다 (Postman/대시보드용).

구조: routes → repository → db → mappers → DTO → serialize → JSON
"""

from binnair_trading_engine.api.main import app, run

__all__ = ["app", "run"]
