"""
Model artifact metadata.
.pt 가중치, scaler, feature order 경로 및 버전 추적.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelArtifactMetadata:
    """
    TorchPredictor 로드용 artifact 메타데이터.
    학습 파이프라인에서 산출된 경로 및 버전 정보.
    """

    model_path: str
    scaler_path: str | None = None
    feature_order_path: str | None = None
    model_version: str = ""
    feature_set_version: str = ""
    scaler_version: str = ""
