"""
Torch 기반 예측기.
model artifact, scaler, feature order 메타데이터로 1회 로드 후 추론.
torch.no_grad(), eval mode, lifecycle 분리.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from binnair_trading_engine.domain.models import (
    MarketSnapshot,
    Prediction,
    SignalAction,
    TradeContext,
)
from binnair_trading_engine.predictor.artifact import ModelArtifactMetadata
from binnair_trading_engine.predictor.feature_provider import FeatureVectorProvider
from binnair_trading_engine.predictor.interface import Predictor

logger = logging.getLogger(__name__)


class TorchPredictor(Predictor):
    """
    PyTorch 모델 기반 예측기.
    - Startup 시 1회 로드 (lifecycle: 요청마다 reload 하지 않음)
    - torch.no_grad(), eval mode
    - model_version, feature_set_version, scaler_version inference 결과에 포함
    """

    def __init__(
        self,
        artifact: ModelArtifactMetadata,
        feature_provider: FeatureVectorProvider,
    ) -> None:
        self._artifact = artifact
        self._feature_provider = feature_provider
        self._model: Any = None
        self._scaler: Any = None
        self._feature_order: list[str] | None = None
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Startup 시 1회 로드. 모델, scaler, feature order."""
        import torch

        model_path = Path(self._artifact.model_path)
        if not model_path.exists():
            logger.warning(
                "model artifact not found, using fallback HOLD: %s",
                self._artifact.model_path,
            )
            return

        try:
            self._model = torch.load(model_path, map_location="cpu", weights_only=True)
            if hasattr(self._model, "eval"):
                self._model.eval()
        except TypeError:
            try:
                self._model = torch.load(model_path, map_location="cpu")
                if hasattr(self._model, "eval"):
                    self._model.eval()
            except Exception as e:
                logger.warning("model load failed, using fallback: %s", e)
                self._model = None
                return
        except Exception as e:
            logger.warning("model load failed, using fallback: %s", e)
            return

        if self._artifact.scaler_path:
            sp = Path(self._artifact.scaler_path)
            if sp.exists():
                try:
                    self._scaler = torch.load(sp, map_location="cpu", weights_only=True)
                except (TypeError, Exception):
                    try:
                        self._scaler = torch.load(sp, map_location="cpu")
                    except Exception as e:
                        logger.warning("scaler load failed: %s", e)

        if self._artifact.feature_order_path:
            fp = Path(self._artifact.feature_order_path)
            if fp.exists():
                try:
                    with open(fp, encoding="utf-8") as f:
                        data = json.load(f)
                    self._feature_order = (
                        data.get("features", data)
                        if isinstance(data, dict)
                        else data
                    )
                except Exception as e:
                    logger.warning("feature order load failed: %s", e)

    def predict(
        self, snapshot: MarketSnapshot, ctx: TradeContext
    ) -> Prediction | None:
        import torch

        if self._model is None:
            return Prediction(
                action=SignalAction.HOLD,
                confidence=0.0,
                price_hint=snapshot.price,
                model_version=self._artifact.model_version,
                feature_set_version=self._artifact.feature_set_version,
                scaler_version=self._artifact.scaler_version,
            )

        try:
            vec = self._feature_provider.get_feature_vector(snapshot, ctx)
            if self._scaler is not None and hasattr(self._scaler, "transform"):
                import numpy as np

                arr = np.array([vec], dtype=np.float32)
                arr = self._scaler.transform(arr)
                vec = arr[0].tolist()

            x = torch.tensor([vec], dtype=torch.float32)
            with torch.no_grad():
                if hasattr(self._model, "eval"):
                    self._model.eval()
                out = self._model(x)

            probs = self._logits_to_probability(out)
            action, confidence = self._to_action(probs)
            score = self._to_score(probs)

            return Prediction(
                action=action,
                confidence=confidence,
                price_hint=snapshot.price,
                score=score,
                probability=probs,
                model_version=self._artifact.model_version,
                feature_set_version=self._artifact.feature_set_version,
                scaler_version=self._artifact.scaler_version,
            )
        except Exception as e:
            logger.exception("inference failed: %s", e)
            return Prediction(
                action=SignalAction.HOLD,
                confidence=0.0,
                price_hint=snapshot.price,
                model_version=self._artifact.model_version,
                feature_set_version=self._artifact.feature_set_version,
                scaler_version=self._artifact.scaler_version,
            )

    def _logits_to_probability(self, out: Any) -> dict[str, float]:
        import torch

        if hasattr(out, "logits"):
            logits = out.logits
        else:
            logits = out

        if isinstance(logits, torch.Tensor):
            probs = torch.softmax(logits, dim=-1)
            p = probs[0].tolist()
        else:
            p = (
                logits[0].tolist()
                if hasattr(logits[0], "tolist")
                else list(logits)[0]
                if hasattr(logits, "__len__")
                else [1.0 / 3, 1.0 / 3, 1.0 / 3]
            )

        actions = [
            SignalAction.BUY.value,
            SignalAction.SELL.value,
            SignalAction.HOLD.value,
        ]
        if len(p) >= 3:
            return {a: float(p[i]) for i, a in enumerate(actions[:3])}
        return {a: 1.0 / 3 for a in actions}

    def _to_action(self, probs: dict[str, float]) -> tuple[SignalAction, float]:
        best = max(probs.items(), key=lambda x: x[1])
        action = SignalAction(best[0])
        confidence = best[1]
        return action, confidence

    def _to_score(self, probs: dict[str, float]) -> float:
        """표준화 스코어 -1~1. BUY=1, SELL=-1, HOLD=0."""
        b = probs.get("BUY", 0.0)
        s = probs.get("SELL", 0.0)
        return float(b - s)
