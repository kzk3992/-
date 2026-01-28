from __future__ import annotations

import datetime as dt
import lzma
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import requests

from .config import RAW_DIR, RAW_FILENAME_TEMPLATE
from .utils import ensure_dir, get_logger

DUKASCOPY_BASE = "https://datafeed.dukascopy.com/datafeed"
CANDLE_RECORD_STRUCT = struct.Struct(">6I"
)  # time, open, high, low, close, volume
PRICE_SCALE = 100000.0


@dataclass
class Candle:
    timestamp: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _dukascopy_month(dt_obj: dt.date) -> str:
    return f"{dt_obj.month - 1:02d}"


def _hour_url(pair: str, day: dt.date, hour: int, granularity: str) -> str:
    return (
        f"{DUKASCOPY_BASE}/{pair}/{day.year}/"
        f"{_dukascopy_month(day)}/{day.day:02d}/{hour:02d}h_{granularity}.bi5"
    )


def _parse_hour_data(payload: bytes, hour_start: dt.datetime) -> List[Candle]:
    candles: List[Candle] = []
    if not payload:
        return candles
    decompressed = lzma.decompress(payload)
    for offset in range(0, len(decompressed), CANDLE_RECORD_STRUCT.size):
        chunk = decompressed[offset : offset + CANDLE_RECORD_STRUCT.size]
        if len(chunk) < CANDLE_RECORD_STRUCT.size:
            continue
        millis, open_p, high_p, low_p, close_p, volume = CANDLE_RECORD_STRUCT.unpack(
            chunk
        )
        candle_time = hour_start + dt.timedelta(milliseconds=millis)
        candles.append(
            Candle(
                timestamp=candle_time,
                open=open_p / PRICE_SCALE,
                high=high_p / PRICE_SCALE,
                low=low_p / PRICE_SCALE,
                close=close_p / PRICE_SCALE,
                volume=float(volume),
            )
        )
    return candles


def _fetch_hour(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int,
    backoff: float,
    logger,
) -> bytes | None:
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.content
            if response.status_code == 404:
                return None
            logger.warning("Unexpected status %s for %s", response.status_code, url)
        except requests.RequestException as exc:
            logger.warning("Download failed (%s/%s): %s", attempt, retries, exc)
        time.sleep(backoff * attempt)
    return None


def _iter_days(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


def download_range(
    start: dt.date,
    end: dt.date,
    pair: str,
    granularity: str,
    output_dir: Path = RAW_DIR,
    timeout: int = 20,
    retries: int = 3,
    backoff: float = 1.5,
) -> None:
    logger = get_logger()
    ensure_dir(output_dir)
    session = requests.Session()

    for day in _iter_days(start, end):
        filename = RAW_FILENAME_TEMPLATE.format(
            pair=pair.lower(), granularity=granularity, date=day.strftime("%Y%m%d")
        )
        output_path = output_dir / filename
        if output_path.exists():
            logger.info("Skipping existing %s", output_path.name)
            continue
        logger.info("Downloading %s", day)
        candles: List[Candle] = []
        for hour in range(24):
            hour_start = dt.datetime(day.year, day.month, day.day, hour, tzinfo=dt.timezone.utc)
            url = _hour_url(pair, day, hour, granularity)
            payload = _fetch_hour(session, url, timeout, retries, backoff, logger)
            if payload is None:
                continue
            candles.extend(_parse_hour_data(payload, hour_start))
        if not candles:
            logger.warning("No data for %s", day)
            continue
        candles.sort(key=lambda c: c.timestamp)
        with output_path.open("w", encoding="utf-8") as f:
            f.write("timestamp,open,high,low,close,volume\n")
            for candle in candles:
                f.write(
                    f"{candle.timestamp.isoformat()},"
                    f"{candle.open:.5f},{candle.high:.5f},{candle.low:.5f},"
                    f"{candle.close:.5f},{candle.volume:.2f}\n"
                )
        logger.info("Saved %s", output_path)
