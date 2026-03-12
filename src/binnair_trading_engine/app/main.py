"""엔진 메인 엔트리포인트."""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path


def main() -> int:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(description="BinnAIR 자동매매 엔진")
    parser.add_argument("-c", "--config", type=str, default=None, help="설정 YAML 경로")
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="run_cycle 간격(초)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from binnair_trading_engine.app.bootstrap import bootstrap

    engine = bootstrap(args.config)
    engine.start()

    def _shutdown(*_: object) -> None:
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            engine.run_cycle()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
