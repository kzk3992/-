from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketData:
    timeframe: str
    time: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray | None


def load_timeframe_csv(
    base_dir: Path,
    timeframe: str,
    file_pattern: str,
    time_column: str,
) -> MarketData:
    path = base_dir / file_pattern.format(timeframe=timeframe)
    logger.info("Loading CSV: %s", path)
    df = pd.read_csv(path)
    if time_column not in df.columns:
        raise ValueError(f"Missing time column '{time_column}' in {path}")
    df = df.sort_values(time_column)
    time = pd.to_datetime(df[time_column], utc=True).astype("int64").to_numpy()
    data = MarketData(
        timeframe=timeframe,
        time=time,
        open=df["open"].to_numpy(dtype=np.float64),
        high=df["high"].to_numpy(dtype=np.float64),
        low=df["low"].to_numpy(dtype=np.float64),
        close=df["close"].to_numpy(dtype=np.float64),
        volume=df["volume"].to_numpy(dtype=np.float64) if "volume" in df.columns else None,
    )
    return data


def load_all_timeframes(
    base_dir: Path,
    timeframes: Iterable[str],
    file_pattern: str,
    time_column: str,
) -> Dict[str, MarketData]:
    data: Dict[str, MarketData] = {}
    for timeframe in timeframes:
        data[timeframe] = load_timeframe_csv(base_dir, timeframe, file_pattern, time_column)
    return data
