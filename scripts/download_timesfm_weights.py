#!/usr/bin/env python3
"""
TimesFM 사전학습 가중치 다운로드/로컬 캐시 준비 스크립트.

새 환경에서 자동매매 엔진을 실행하기 전에 한 번 실행해 두면,
이후 TimesFM Predictor는 Hugging Face 로컬 캐시의 모델 파일을 재사용한다.
"""
from __future__ import annotations

import argparse
import sys
import time


DEFAULT_MODEL_ID = "google/timesfm-2.5-200m-pytorch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and cache pretrained TimesFM weights."
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help=f"Hugging Face model ID. Default: {DEFAULT_MODEL_ID}",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a tiny forecast after loading to verify inference works.",
    )
    return parser.parse_args()


def load_model(model_id: str):
    import timesfm

    if model_id != DEFAULT_MODEL_ID:
        raise ValueError(
            "현재 스크립트는 TimesFM 2.5 200M torch 로더를 사용합니다. "
            f"다른 model-id를 쓰려면 로더 매핑을 추가해야 합니다: {model_id}"
        )

    return timesfm.TimesFM_2p5_200M_torch.from_pretrained(model_id)


def run_smoke_test(model) -> None:
    import numpy as np
    import timesfm

    model.compile(
        timesfm.ForecastConfig(
            max_context=128,
            max_horizon=3,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=True,
            fix_quantile_crossing=True,
        )
    )
    point_forecast, quantile_forecast = model.forecast(
        horizon=3,
        inputs=[np.linspace(100.0, 101.0, 64)],
    )
    print("Smoke test forecast shape:", point_forecast.shape)
    print("Smoke test quantile shape:", quantile_forecast.shape)


def main() -> int:
    args = parse_args()
    started_at = time.perf_counter()

    print(f"Loading TimesFM weights: {args.model_id}")
    model = load_model(args.model_id)
    elapsed = time.perf_counter() - started_at
    print(f"Loaded: {type(model).__name__} ({elapsed:.1f}s)")

    if args.smoke_test:
        run_smoke_test(model)

    return 0


if __name__ == "__main__":
    sys.exit(main())
