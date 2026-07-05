"""
조회 API 패키지.

매매 엔진과 분리된 read-only FastAPI 레이어.

레이어 구조:
  controllers/  → HTTP·WebSocket 라우트
  services/     → 거래소·실시간 스트림
  repositories/ → Postgres read-only
  dto/          → API 응답 DTO
  common/       → DB 세션, 매퍼, 직렬화
"""

from binnair_trading_engine.api.main import app, run

__all__ = ["app", "run"]
