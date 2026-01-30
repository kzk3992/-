from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class DrawdownStats:
    max_dd_pips: float
    max_dd_pct: float


def compute_drawdown(equity_curve: List[float]) -> DrawdownStats:
    if not equity_curve:
        return DrawdownStats(0.0, 0.0)
    peak = equity_curve[0]
    max_dd_abs = 0.0
    max_dd_pct = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = peak - value
        max_dd_abs = max(max_dd_abs, dd)
        max_dd_pct = max(max_dd_pct, (dd / peak) * 100 if peak > 0 else 0.0)
    return DrawdownStats(max_dd_abs, max_dd_pct)


def monthly_pips_stats(times: np.ndarray, pips: List[float]) -> Tuple[float, float, Dict[str, float]]:
    if not pips:
        return 0.0, 0.0, {}
    months: Dict[str, float] = {}
    for timestamp, pip in zip(times, pips, strict=False):
        month = np.datetime64(int(timestamp), "ns").astype("datetime64[M]").astype(str)
        months[month] = months.get(month, 0.0) + pip
    values = np.array(list(months.values()), dtype=np.float64)
    return float(values.mean()), float(values.std(ddof=0)), months


def max_consecutive_losses(pips: List[float]) -> int:
    max_losses = 0
    current = 0
    for pip in pips:
        if pip <= 0:
            current += 1
            max_losses = max(max_losses, current)
        else:
            current = 0
    return max_losses
