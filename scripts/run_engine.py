#!/usr/bin/env python3
"""엔진 실행 스크립트."""

import argparse
import logging
import signal
import sys
from pathlib import Path

# src 상위에서 실행 가정
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binnair_trading_engine.app.bootstrap import bootstrap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, default=None)
    args = parser.parse_args()

    engine = bootstrap(args.config)
    engine.start()

    def shutdown(*_: object) -> None:
        engine.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            engine.run_cycle()
            # TODO: 폴링 간격 또는 이벤트 대기
            import time
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
