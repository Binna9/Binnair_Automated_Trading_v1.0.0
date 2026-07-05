"""
DTO → JSON 변환.

datetime을 ISO 문자열로 바꾸고, dataclass를 dict로 직렬화한다.

왜 필요: FastAPI가 JSON으로 내려주려면 Python 객체를 dict 형태로
바꿔야 한다. repository DTO를 HTTP 응답 body로 만드는 마지막 단계.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any


def dto_to_dict(dto: Any) -> dict[str, Any]:
    """DTO/dataclass를 JSON 직렬화 가능 dict로 변환."""
    if is_dataclass(dto):
        out: dict[str, Any] = {}
        for key, value in asdict(dto).items():
            if isinstance(value, datetime):
                out[key] = value.isoformat()
            elif is_dataclass(value):
                out[key] = dto_to_dict(value)
            elif isinstance(value, list):
                out[key] = [
                    dto_to_dict(v) if is_dataclass(v) else v for v in value
                ]
            else:
                out[key] = value
        return out
    return dict(dto)


def serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [serialize(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return dto_to_dict(value)
    return value
