"""
Binance USD-M Futures User Data Stream listenKey 관리.

POST/PUT/DELETE /fapi/v1/listenKey — 서명 없이 API Key 헤더만 필요.
"""

from __future__ import annotations

import logging

import httpx

from binnair_trading_engine.exchange.binance_endpoints import normalize_rest_base_url

logger = logging.getLogger(__name__)


class BinanceListenKeyClient:
    """REST base_url 기준 listenKey 생성·연장·삭제."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = normalize_rest_base_url(base_url)
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self._api_key}

    def create(self) -> str:
        url = f"{self._base_url}/fapi/v1/listenKey"
        resp = httpx.post(url, headers=self._headers(), timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        key = data.get("listenKey", "")
        if not key:
            raise RuntimeError("listenKey missing in Binance response")
        return str(key)

    def keepalive(self, listen_key: str) -> None:
        url = f"{self._base_url}/fapi/v1/listenKey"
        resp = httpx.put(
            url,
            headers=self._headers(),
            params={"listenKey": listen_key},
            timeout=self._timeout,
        )
        resp.raise_for_status()

    def close(self, listen_key: str) -> None:
        url = f"{self._base_url}/fapi/v1/listenKey"
        try:
            resp = httpx.delete(
                url,
                headers=self._headers(),
                params={"listenKey": listen_key},
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.debug("listenKey close failed: %s", e)
