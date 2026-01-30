from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from report_utils import compute_drawdown, max_consecutive_losses, monthly_pips_stats
from strategy_bits import (
    BIT_ENTRY_A,
    BIT_ENTRY_B,
    BIT_EXIT_REVERSE,
    BIT_HALF_TP,
    BIT_MANAGE_A,
    BIT_MANAGE_B,
    BIT_MOVE_BE,
    BIT_SL_ATR,
    BIT_SL_FIXED,
    BIT_SL_STRUCT,
    BIT_TP_ATR_TRAIL,
    BIT_TP_DONCHIAN,
    BIT_TP_EMA,
    BIT_TP_FIXED,
    BIT_TP_TIMEOUT,
    BIT_TIMEFILTER_0,
    BIT_TIMEFILTER_1,
    bit_is_on,
)


@dataclass
class Trade:
    trade_id: int
    entry_time: int
    exit_time: int
    direction: int
    entry_price: float
    exit_price: float
    pips: float
    holding_minutes: float


@dataclass
class Summary:
    strategy_id: int
    total_trades: int
    win_rate_total: float
    pips_total: float
    avg_pips_per_trade: float
    max_dd_pips: float
    max_consecutive_losses: int
    monthly_pips_avg: float
    monthly_pips_std: float
    compound_return_pct: float
    max_dd_pct: float
    stopped_reason: str


def _time_filter_allows(timestamp: int, strategy_id: int) -> bool:
    hour = np.datetime64(int(timestamp), "ns").astype("datetime64[h]").astype(int) % 24
    if bit_is_on(strategy_id, BIT_TIMEFILTER_0) and 7 <= hour <= 22:
        return True
    if bit_is_on(strategy_id, BIT_TIMEFILTER_1) and (hour <= 2 or hour >= 20):
        return True
    return False


def simulate_strategy(
    strategy_id: int,
    time: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    indicators: Dict[str, np.ndarray],
    config: Dict[str, float],
    export_trades: bool = False,
) -> Tuple[Summary, List[Trade]]:
    equity = config["initial_equity"]
    risk_per_trade = config["risk_per_trade"]
    pip_size = config["pip_size"]
    spread_pips = config["spread_pips"]
    fee_per_trade = config["fee_per_trade"]
    max_dd_pct_stop = config["max_dd_pct_stop"]
    early_stop_min_trades = int(config["early_stop_min_trades"])
    early_stop_max_losses = int(config["early_stop_max_losses"])
    early_stop_enabled = bool(config["early_stop_enabled"])

    ema_fast = indicators["ema_fast"]
    ema_slow = indicators["ema_slow"]
    atr = indicators["atr"]
    donchian_high = indicators["donchian_high"]
    donchian_low = indicators["donchian_low"]

    trades: List[Trade] = []
    trade_pips: List[float] = []
    trade_times: List[int] = []
    equity_curve: List[float] = [equity]

    position = 0
    entry_price = 0.0
    entry_time = 0
    stop_price = 0.0
    take_profit = 0.0
    trade_id = 0
    half_taken = False
    max_equity = equity
    stopped_reason = "finished"

    for i in range(1, len(close)):
        if not _time_filter_allows(time[i], strategy_id):
            continue

        if position == 0:
            entry_a = bit_is_on(strategy_id, BIT_ENTRY_A)
            entry_b = bit_is_on(strategy_id, BIT_ENTRY_B)
            if entry_a and ema_fast[i] > ema_slow[i] and ema_fast[i - 1] <= ema_slow[i - 1]:
                position = 1
            elif entry_b and ema_fast[i] < ema_slow[i] and ema_fast[i - 1] >= ema_slow[i - 1]:
                position = -1

            if position != 0:
                entry_price = open_[i] + (spread_pips * pip_size * position)
                entry_time = time[i]
                sl_pips = 20.0
                if bit_is_on(strategy_id, BIT_SL_ATR):
                    sl_pips = atr[i] / pip_size * 2.0
                elif bit_is_on(strategy_id, BIT_SL_FIXED):
                    sl_pips = 15.0
                elif bit_is_on(strategy_id, BIT_SL_STRUCT):
                    sl_pips = abs(entry_price - (donchian_low[i] if position > 0 else donchian_high[i])) / pip_size
                stop_price = entry_price - position * sl_pips * pip_size
                take_profit = entry_price + position * sl_pips * pip_size * 2.0
                if bit_is_on(strategy_id, BIT_TP_FIXED):
                    take_profit = entry_price + position * 20.0 * pip_size
                half_taken = False
        else:
            exit_reason = None
            exit_price = None

            if position > 0:
                if low[i] <= stop_price:
                    exit_reason = "sl"
                    exit_price = stop_price
                elif high[i] >= take_profit:
                    exit_reason = "tp"
                    exit_price = take_profit
            else:
                if high[i] >= stop_price:
                    exit_reason = "sl"
                    exit_price = stop_price
                elif low[i] <= take_profit:
                    exit_reason = "tp"
                    exit_price = take_profit

            if exit_reason is None:
                if bit_is_on(strategy_id, BIT_TP_DONCHIAN):
                    if position > 0 and close[i] < donchian_low[i]:
                        exit_reason = "donchian"
                        exit_price = close[i]
                    elif position < 0 and close[i] > donchian_high[i]:
                        exit_reason = "donchian"
                        exit_price = close[i]

            if exit_reason is None and bit_is_on(strategy_id, BIT_TP_EMA):
                if position > 0 and close[i] < ema_fast[i]:
                    exit_reason = "ema"
                    exit_price = close[i]
                elif position < 0 and close[i] > ema_fast[i]:
                    exit_reason = "ema"
                    exit_price = close[i]

            if exit_reason is None and bit_is_on(strategy_id, BIT_TP_TIMEOUT):
                holding_minutes = (time[i] - entry_time) / (60 * 1_000_000_000)
                if holding_minutes >= 180:
                    exit_reason = "timeout"
                    exit_price = close[i]

            if exit_reason is None and bit_is_on(strategy_id, BIT_EXIT_REVERSE):
                if position > 0 and ema_fast[i] < ema_slow[i]:
                    exit_reason = "reverse"
                    exit_price = close[i]
                elif position < 0 and ema_fast[i] > ema_slow[i]:
                    exit_reason = "reverse"
                    exit_price = close[i]

            if exit_reason is None and bit_is_on(strategy_id, BIT_TP_ATR_TRAIL):
                trail_distance = atr[i] * 1.5
                if position > 0:
                    stop_price = max(stop_price, close[i] - trail_distance)
                else:
                    stop_price = min(stop_price, close[i] + trail_distance)

            if exit_reason is None and bit_is_on(strategy_id, BIT_HALF_TP) and not half_taken:
                target = entry_price + position * abs(entry_price - stop_price) * 1.0
                if (position > 0 and high[i] >= target) or (position < 0 and low[i] <= target):
                    half_taken = True

            if exit_reason is None and bit_is_on(strategy_id, BIT_MOVE_BE) and half_taken:
                stop_price = entry_price

            if exit_reason:
                exit_price = float(exit_price)
                pips = (exit_price - entry_price) / pip_size * position - spread_pips
                equity += equity * risk_per_trade * (pips / abs(entry_price - stop_price) / pip_size) - fee_per_trade
                trade_pips.append(pips)
                trade_times.append(time[i])
                equity_curve.append(equity)
                if equity > max_equity:
                    max_equity = equity
                if equity <= 0:
                    stopped_reason = "bankrupt"
                    break
                dd_pct = (max_equity - equity) / max_equity * 100 if max_equity > 0 else 0.0
                if dd_pct >= max_dd_pct_stop:
                    stopped_reason = "dd_stop"
                    break

                if export_trades:
                    holding_minutes = (time[i] - entry_time) / (60 * 1_000_000_000)
                    trades.append(
                        Trade(
                            trade_id=trade_id,
                            entry_time=entry_time,
                            exit_time=time[i],
                            direction=position,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            pips=pips,
                            holding_minutes=holding_minutes,
                        )
                    )
                trade_id += 1
                position = 0

        if early_stop_enabled and len(trade_pips) >= early_stop_min_trades:
            if max_consecutive_losses(trade_pips) >= early_stop_max_losses:
                stopped_reason = "early_stop"
                break

    total_trades = len(trade_pips)
    win_rate = (sum(1 for p in trade_pips if p > 0) / total_trades * 100) if total_trades else 0.0
    pips_total = float(sum(trade_pips))
    avg_pips = pips_total / total_trades if total_trades else 0.0
    drawdown = compute_drawdown(equity_curve)
    monthly_avg, monthly_std, _ = monthly_pips_stats(np.array(trade_times), trade_pips)

    summary = Summary(
        strategy_id=strategy_id,
        total_trades=total_trades,
        win_rate_total=win_rate,
        pips_total=pips_total,
        avg_pips_per_trade=avg_pips,
        max_dd_pips=drawdown.max_dd_pips,
        max_consecutive_losses=max_consecutive_losses(trade_pips),
        monthly_pips_avg=monthly_avg,
        monthly_pips_std=monthly_std,
        compound_return_pct=(equity - config["initial_equity"]) / config["initial_equity"] * 100,
        max_dd_pct=drawdown.max_dd_pct,
        stopped_reason=stopped_reason,
    )
    return summary, trades
