from __future__ import annotations

import numpy as np


def ema(values: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1.0)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    tr = np.empty_like(close)
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = np.empty_like(tr)
    out[0] = tr[0]
    alpha = 1.0 / period
    for i in range(1, len(tr)):
        out[i] = alpha * tr[i] + (1 - alpha) * out[i - 1]
    return out


def rolling_max(values: np.ndarray, window: int) -> np.ndarray:
    out = np.empty_like(values)
    for i in range(len(values)):
        start = max(0, i - window + 1)
        out[i] = np.max(values[start : i + 1])
    return out


def rolling_min(values: np.ndarray, window: int) -> np.ndarray:
    out = np.empty_like(values)
    for i in range(len(values)):
        start = max(0, i - window + 1)
        out[i] = np.min(values[start : i + 1])
    return out


def compute_indicators(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "ema_fast": ema(close, 10),
        "ema_slow": ema(close, 30),
        "atr": atr(high, low, close, 14),
        "donchian_high": rolling_max(high, 20),
        "donchian_low": rolling_min(low, 20),
    }
