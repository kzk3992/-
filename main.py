from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from src.config import CLEAN_DIR, CLEAN_FILENAME, EVENTS_DIR, EVENTS_FILENAME, RAW_DIR
from src.download_dukas import download_range
from src.poisson_model import compute_poisson
from src.preprocess import preprocess_raw
from src.detect_swans import detect_swans
from src.plotting import plot_heatmaps
from src.utils import get_logger


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="USDJPY black swan analysis toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download data from Dukascopy")
    download.add_argument("--start", required=True, type=parse_date)
    download.add_argument("--end", required=True, type=parse_date)
    download.add_argument("--pair", default="USDJPY")
    download.add_argument("--granularity", default="1m")
    download.add_argument("--output-dir", type=Path, default=RAW_DIR)

    preprocess = subparsers.add_parser("preprocess", help="Preprocess raw CSV data")
    preprocess.add_argument("--input-dir", type=Path, default=RAW_DIR)
    preprocess.add_argument("--output-dir", type=Path, default=CLEAN_DIR)
    preprocess.add_argument("--output-filename", default=CLEAN_FILENAME)

    detect = subparsers.add_parser("detect", help="Detect black swan events")
    detect.add_argument("--input", type=Path, default=CLEAN_DIR / CLEAN_FILENAME)
    detect.add_argument("--window-minutes", type=int, default=5)
    detect.add_argument("--threshold-pips", type=float, default=50)
    detect.add_argument("--decluster-minutes", type=int, default=30)
    detect.add_argument("--output-dir", type=Path, default=EVENTS_DIR)
    detect.add_argument("--output-filename", default=EVENTS_FILENAME)

    poisson = subparsers.add_parser("poisson", help="Estimate Poisson parameters")
    poisson.add_argument("--clean", type=Path, default=CLEAN_DIR / CLEAN_FILENAME)
    poisson.add_argument("--events", type=Path, default=EVENTS_DIR / EVENTS_FILENAME)
    poisson.add_argument("--output-dir", type=Path, default=Path("reports"))

    plot = subparsers.add_parser("plot", help="Plot heatmaps")
    plot.add_argument("--lambda-csv", type=Path, default=Path("reports/lambda_by_month_timeband.csv"))
    plot.add_argument(
        "--prob-csv", type=Path, default=Path("reports/probability_by_month_timeband.csv")
    )
    plot.add_argument("--output-dir", type=Path, default=Path("reports"))

    return parser


def main() -> None:
    logger = get_logger()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "download":
        download_range(args.start, args.end, args.pair, args.granularity, args.output_dir)
    elif args.command == "preprocess":
        preprocess_raw(args.input_dir, args.output_dir, args.output_filename)
    elif args.command == "detect":
        detect_swans(
            args.input,
            args.window_minutes,
            args.threshold_pips,
            args.decluster_minutes,
            args.output_dir,
            args.output_filename,
        )
    elif args.command == "poisson":
        compute_poisson(args.clean, args.events, args.output_dir)
    elif args.command == "plot":
        plot_heatmaps(args.lambda_csv, args.prob_csv, args.output_dir)
    else:
        logger.error("Unknown command")


if __name__ == "__main__":
    main()
