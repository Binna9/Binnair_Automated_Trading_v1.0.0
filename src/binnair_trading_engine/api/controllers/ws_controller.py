"""
WebSocket live account stream routes.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from binnair_trading_engine.api.services.live_hub import get_live_hub

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/v1/live")
async def websocket_live(
    websocket: WebSocket,
    symbol: str | None = Query(default=None, description="포지션 필터 (미지정=config symbol)"),
) -> None:
    """
    실시간 지갑·포지션·체결 스트림.

    연결 직후 snapshot + stream_status 전송, 이후 Binance User Data Stream 이벤트 push.
    클라이언트 → `{"action":"refresh"}` 로 REST 스냅샷 재조회 가능.
    """
    hub = get_live_hub()
    await hub.register(websocket)
    bridge = getattr(websocket.app.state, "live_bridge", None)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("action") == "refresh" and bridge is not None:
                await bridge.refresh_snapshot()
            elif msg.get("action") == "pong":
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("websocket live closed: %s", e)
    finally:
        await hub.unregister(websocket)
