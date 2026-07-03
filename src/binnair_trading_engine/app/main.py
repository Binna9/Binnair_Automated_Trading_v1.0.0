"""
자동매매 엔진 CLI 진입점이다.
설정 파일을 받아 market data polling 루프를 실행하고 종료 신호를 처리한다.
"""

import argparse
import atexit
import logging
import signal
import sys
import time


def main() -> int:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(description="BinnAIR 자동매매 엔진")
    parser.add_argument("-c", "--config", type=str, default=None, help="설정 YAML 경로")
    parser.add_argument(
        "-i", "--interval", type=float, default=None,
        help="run_cycle 간격(초). market_data.enabled 시 poll_interval_seconds 사용",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from binnair_trading_engine.app.bootstrap import bootstrap
    from binnair_trading_engine.market_data import create_market_data_provider

    engine = bootstrap(args.config)
    md_cfg = engine._config.market_data

    provider = None
    if md_cfg.enabled:
        provider = create_market_data_provider(
            provider_type=md_cfg.provider,
            base_url=md_cfg.base_url,
            timeout=md_cfg.timeout,
        )
        interval = args.interval if args.interval is not None else md_cfg.poll_interval_seconds
        symbol = md_cfg.symbol
    else:
        interval = args.interval if args.interval is not None else 1.0

    engine.start()
    running = True

    def _shutdown(*_: object) -> None:
        nonlocal running
        running = False

    atexit.register(engine.stop)
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _shutdown)

    try:
        while running:
            if provider is not None:
                snapshot = provider.fetch_snapshot(symbol, run_id=engine._ctx.run_id)
                if snapshot:
                    engine.run_cycle(snapshot)
                else:
                    engine.run_cycle()  # heartbeat
            else:
                engine.run_cycle()
            # sleep을 쪼개야 Ctrl+C/SIGTERM 시 빠르게 stop() 진입
            slept = 0.0
            while running and slept < interval:
                chunk = min(1.0, interval - slept)
                time.sleep(chunk)
                slept += chunk
    except KeyboardInterrupt:
        running = False
    finally:
        engine.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
