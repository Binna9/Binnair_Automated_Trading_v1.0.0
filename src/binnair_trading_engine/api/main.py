"""
FastAPI 앱 진입점.

- create_app(): FastAPI 인스턴스 생성 (CORS, 라우트 등록)
- run(): uvicorn으로 서버 기동 (host/port는 BINNAIR_API_* 환경변수)

왜 필요: HTTP 서버를 켜고 `/docs`, Postman 요청을 받는 시작점.
엔진 core.py 와는 별도 프로세스로 실행한다.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from binnair_trading_engine.api.controllers.autopilot_controller import (
    router as autopilot_router,
)
from binnair_trading_engine.api.controllers.control_controller import (
    router as control_router,
)
from binnair_trading_engine.api.controllers.flow_controller import router
from binnair_trading_engine.api.controllers.history_controller import router as history_router
from binnair_trading_engine.api.controllers.ws_controller import router as ws_router
from binnair_trading_engine.api.deps import load_config_path
from binnair_trading_engine.api.services.live_bridge import BinanceLiveBridge
from binnair_trading_engine.api.services.live_hub import get_live_hub
from binnair_trading_engine.config import load_config


@asynccontextmanager
async def _lifespan(application: FastAPI):
    load_config_path()
    cfg = load_config()
    hub = get_live_hub()
    bridge = BinanceLiveBridge(cfg, hub)
    application.state.live_hub = hub
    application.state.live_bridge = bridge

    bridge_task: asyncio.Task | None = None
    if cfg.api.enabled and cfg.api.live_stream.enabled:
        bridge_task = asyncio.create_task(bridge.run(), name="binance-live-bridge")

    yield

    if bridge_task is not None:
        await bridge.stop()
        bridge_task.cancel()
        await asyncio.gather(bridge_task, return_exceptions=True)


def create_app() -> FastAPI:
    load_config_path()
    cfg = load_config()
    api_cfg = cfg.api

    application = FastAPI(
        title="BinnAIR Trading Monitor API",
        description="자동매매 DB 이력 조회 + 실시간 계정 WebSocket",
        version="1.1.0",
        lifespan=_lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=api_cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )

    application.include_router(router)
    application.include_router(autopilot_router)
    application.include_router(control_router)
    application.include_router(history_router)
    application.include_router(ws_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()


def run(host: str | None = None, port: int | None = None) -> None:
    import uvicorn

    load_config_path()
    cfg = load_config()
    bind_host = host if host is not None else cfg.api.host
    bind_port = port if port is not None else cfg.api.port

    uvicorn.run(
        "binnair_trading_engine.api.main:app",
        host=bind_host,
        port=bind_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
