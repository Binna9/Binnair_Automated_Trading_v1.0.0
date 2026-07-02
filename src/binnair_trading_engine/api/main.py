"""
FastAPI 앱 진입점.

- create_app(): FastAPI 인스턴스 생성 (CORS, 라우트 등록)
- run(): uvicorn으로 서버 기동 (host/port는 config.yaml api 섹션)

왜 필요: HTTP 서버를 켜고 `/docs`, Postman 요청을 받는 시작점.
엔진 core.py 와는 별도 프로세스로 실행한다.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from binnair_trading_engine.api.deps import load_config_path
from binnair_trading_engine.api.routes import router
from binnair_trading_engine.config import load_config


def create_app() -> FastAPI:
    load_config_path()
    cfg = load_config()
    api_cfg = cfg.api

    application = FastAPI(
        title="BinnAIR Trading Monitor API",
        description="자동매매 DB 이력 조회 (read-only)",
        version="1.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=api_cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    application.include_router(router)

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
