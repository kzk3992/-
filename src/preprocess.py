from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import CLEAN_DIR, CLEAN_FILENAME, RAW_DIR
from .utils import ensure_dir, get_logger


def preprocess_raw(
    input_dir: Path = RAW_DIR,
    output_dir: Path = CLEAN_DIR,
    output_filename: str = CLEAN_FILENAME,
) -> Path:
    logger = get_logger()
    ensure_dir(output_dir)
    files = sorted(input_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files in {input_dir}")
    frames = []
    for path in files:
        logger.info("Reading %s", path.name)
        df = pd.read_csv(path)
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
    combined = combined.sort_values("timestamp")
    combined = combined.drop_duplicates(subset=["timestamp"], keep="first")
    combined["datetime_jst"] = combined["timestamp"].dt.tz_convert("Asia/Tokyo")
    combined["datetime_jst_naive"] = combined["datetime_jst"].dt.tz_localize(None)
    output_path = output_dir / output_filename
    combined.to_csv(output_path, index=False)
    logger.info("Saved cleaned data to %s", output_path)
    return output_path
