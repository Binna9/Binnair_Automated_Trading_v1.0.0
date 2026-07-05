"""TimesFM score 분포 기반 adaptive threshold."""

from __future__ import annotations

from collections import deque


class ThresholdCalibrator:
    """최근 |score| 분포에서 임계값 산출."""

    def __init__(
        self,
        *,
        window: int = 500,
        min_samples: int = 30,
        percentile: float = 70.0,
        k: float = 1.0,
    ) -> None:
        self._window = max(10, window)
        self._min_samples = max(5, min_samples)
        self._percentile = min(99.0, max(50.0, percentile))
        self._k = max(0.1, k)
        self._scores: deque[float] = deque(maxlen=self._window)

    @property
    def sample_count(self) -> int:
        return len(self._scores)

    def record(self, score: float | None) -> None:
        if score is None:
            return
        self._scores.append(abs(float(score)))

    def compute_threshold(self, fee_floor: float, fallback: float) -> float:
        """
        percentile(|score|) × k, fee_floor 이상.
        샘플 부족 시 fallback(설정 signal_threshold 또는 fee_floor).
        """
        floor = max(fee_floor, 0.0)
        if len(self._scores) < self._min_samples:
            return max(floor, fallback)

        sorted_vals = sorted(self._scores)
        idx = int(round((self._percentile / 100.0) * (len(sorted_vals) - 1)))
        idx = max(0, min(idx, len(sorted_vals) - 1))
        adaptive = sorted_vals[idx] * self._k
        return max(floor, adaptive)
