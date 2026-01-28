from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
EVENTS_DIR = DATA_DIR / "events"
REPORTS_DIR = PROJECT_ROOT / "reports"


@dataclass(frozen=True)
class TimeBand:
    code: str
    start_hour: int
    end_hour: int
    crosses_midnight: bool = False


TIME_BANDS = (
    TimeBand("A", 9, 14, False),
    TimeBand("B", 15, 20, False),
    TimeBand("C", 21, 2, True),
    TimeBand("D", 3, 8, False),
)

PIP_SIZE = 0.01
DEFAULT_PAIR = "USDJPY"
DEFAULT_GRANULARITY = "1m"

RAW_FILENAME_TEMPLATE = "{pair}_{granularity}_{date}.csv"
CLEAN_FILENAME = "usdjpy_1m_jst.csv"
EVENTS_FILENAME = "swans.csv"
