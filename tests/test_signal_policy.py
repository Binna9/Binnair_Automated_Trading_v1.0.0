"""ConsecutiveSignalPolicy — long_only / long_short 모드."""

from binnair_trading_engine.domain.models import SignalAction
from binnair_trading_engine.signal.policy import ConsecutiveSignalPolicy


def _fill_history(policy: ConsecutiveSignalPolicy, symbol: str, *actions: SignalAction) -> None:
    for action in actions:
        policy.record(symbol, action)


def test_long_only_allows_buy_entry_only() -> None:
    policy = ConsecutiveSignalPolicy(consecutive_required=2, mode="long_only")
    symbol = "XRPUSDT"
    _fill_history(policy, symbol, SignalAction.SELL, SignalAction.SELL)
    assert not policy.allows_entry_action(symbol, SignalAction.SELL)
    _fill_history(policy, symbol, SignalAction.BUY, SignalAction.BUY)
    assert policy.allows_entry_action(symbol, SignalAction.BUY)
    assert policy.allows_long_exit(symbol) is False
    _fill_history(policy, symbol, SignalAction.SELL, SignalAction.SELL)
    assert policy.allows_long_exit(symbol)


def test_long_short_allows_both_entries() -> None:
    policy = ConsecutiveSignalPolicy(consecutive_required=2, mode="long_short")
    symbol = "XRPUSDT"
    _fill_history(policy, symbol, SignalAction.BUY, SignalAction.BUY)
    assert policy.allows_entry_action(symbol, SignalAction.BUY)
    policy.reset(symbol)
    _fill_history(policy, symbol, SignalAction.SELL, SignalAction.SELL)
    assert policy.allows_entry_action(symbol, SignalAction.SELL)


def test_long_short_exit_signals() -> None:
    policy = ConsecutiveSignalPolicy(consecutive_required=2, mode="long_short")
    symbol = "XRPUSDT"
    _fill_history(policy, symbol, SignalAction.SELL, SignalAction.SELL)
    assert policy.allows_long_exit(symbol)
    assert not policy.allows_short_exit(symbol)
    policy.reset(symbol)
    _fill_history(policy, symbol, SignalAction.BUY, SignalAction.BUY)
    assert policy.allows_short_exit(symbol)
    assert not policy.allows_long_exit(symbol)


def test_long_only_short_exit_disabled() -> None:
    policy = ConsecutiveSignalPolicy(consecutive_required=2, mode="long_only")
    symbol = "XRPUSDT"
    _fill_history(policy, symbol, SignalAction.BUY, SignalAction.BUY)
    assert not policy.allows_short_exit(symbol)
