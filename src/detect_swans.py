from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from .config import EVENTS_DIR, EVENTS_FILENAME, PIP_SIZE
from .utils import ensure_dir, get_logger


@dataclass
class Detection:
    timestamp: dt.datetime
    delta_pips: float


def assign_timeband(timestamp: dt.datetime) -> str:
    hour = timestamp.hour
    if 9 <= hour <= 14:
        return "A"
    if 15 <= hour <= 20:
        return "B"
    if hour >= 21 or hour <= 2:
        return "C"
    return "D"


def decluster_detections(
    detections: Iterable[Detection], decluster_minutes: int
) -> List[Detection]:
    detections_sorted = sorted(detections, key=lambda d: d.timestamp)
    if not detections_sorted:
        return []
    clustered = [detections_sorted[0]]
    for detection in detections_sorted[1:]:
        last_time = clustered[-1].timestamp
        if (detection.timestamp - last_time) > dt.timedelta(minutes=decluster_minutes):
            clustered.append(detection)
    return clustered


def detect_swans(
    clean_path: Path,
    window_minutes: int,
    threshold_pips: float,
    decluster_minutes: int,
    output_dir: Path = EVENTS_DIR,
    output_filename: str = EVENTS_FILENAME,
) -> Path:
    logger = get_logger()
    ensure_dir(output_dir)
    df = pd.read_csv(clean_path, parse_dates=["datetime_jst_naive"])
    df = df.sort_values("datetime_jst_naive")
    df["delta"] = df["close"] - df["close"].shift(window_minutes)
    df["delta_pips"] = df["delta"] / PIP_SIZE
    df["abs_delta_pips"] = df["delta_pips"].abs()
    hits = df[df["abs_delta_pips"] >= threshold_pips].copy()
    detections = [
        Detection(row["datetime_jst_naive"], row["delta_pips"])
        for _, row in hits.iterrows()
    ]
    clustered = decluster_detections(detections, decluster_minutes)
    events = []
    for idx, detection in enumerate(clustered, start=1):
        direction = "UP" if detection.delta_pips >= 0 else "DOWN"
        month = detection.timestamp.strftime("%Y-%m")
        timeband = assign_timeband(detection.timestamp)
        events.append(
            {
                "event_id": idx,
                "detected_at_jst": detection.timestamp,
                "month": month,
                "timeband": timeband,
                "direction": direction,
                "delta_pips": detection.delta_pips,
                "abs_delta_pips": abs(detection.delta_pips),
                "window_minutes": window_minutes,
                "threshold_pips": threshold_pips,
                "decluster_minutes": decluster_minutes,
            }
        )
    events_df = pd.DataFrame(events)
    output_path = output_dir / output_filename
    events_df.to_csv(output_path, index=False)
    logger.info("Saved swan events to %s", output_path)
    return output_path
