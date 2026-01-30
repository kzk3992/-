from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


BIT_TIMEFILTER_0 = 0
BIT_TIMEFILTER_1 = 1
BIT_ENTRY_A = 11
BIT_ENTRY_B = 12
BIT_MANAGE_A = 15
BIT_MANAGE_B = 16

BIT_SL_STRUCT = 18
BIT_SL_ATR = 19
BIT_SL_FIXED = 20

BIT_TP_ATR_TRAIL = 21
BIT_TP_DONCHIAN = 22
BIT_TP_EMA = 23
BIT_TP_TIMEOUT = 24
BIT_TP_FIXED = 25

BIT_HALF_TP = 26
BIT_MOVE_BE = 27
BIT_EXIT_REVERSE = 28


@dataclass(frozen=True)
class StrategyConstraints:
    enforce_entry_exclusive: bool
    enforce_time_filter: bool
    enforce_management_minimum: bool
    enforce_sl_exclusive: bool
    enforce_tp_rules: bool


def bit_is_on(strategy_id: int, bit: int) -> bool:
    return (strategy_id >> bit) & 1 == 1


def validate_strategy(strategy_id: int, constraints: StrategyConstraints) -> bool:
    if constraints.enforce_entry_exclusive:
        entry_a = bit_is_on(strategy_id, BIT_ENTRY_A)
        entry_b = bit_is_on(strategy_id, BIT_ENTRY_B)
        if entry_a == entry_b:
            return False

    if constraints.enforce_time_filter:
        if not (bit_is_on(strategy_id, BIT_TIMEFILTER_0) or bit_is_on(strategy_id, BIT_TIMEFILTER_1)):
            return False

    if constraints.enforce_management_minimum:
        if not (bit_is_on(strategy_id, BIT_MANAGE_A) or bit_is_on(strategy_id, BIT_MANAGE_B)):
            return False

    if constraints.enforce_sl_exclusive:
        sl_bits = sum(
            bit_is_on(strategy_id, bit)
            for bit in (BIT_SL_STRUCT, BIT_SL_ATR, BIT_SL_FIXED)
        )
        if sl_bits != 1:
            return False

    if constraints.enforce_tp_rules:
        tp_bits = [
            bit_is_on(strategy_id, BIT_TP_ATR_TRAIL),
            bit_is_on(strategy_id, BIT_TP_DONCHIAN),
            bit_is_on(strategy_id, BIT_TP_EMA),
            bit_is_on(strategy_id, BIT_TP_TIMEOUT),
            bit_is_on(strategy_id, BIT_TP_FIXED),
        ]
        if not any(tp_bits):
            return False
        if tp_bits[4] and any(tp_bits[:4]):
            return False

    return True


def iter_strategy_ids(start_id: int, end_id: int) -> Iterable[int]:
    for strategy_id in range(start_id, end_id):
        yield strategy_id
