from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import REPORTS_DIR
from .detect_swans import assign_timeband
from .utils import ensure_dir, get_logger


def compute_poisson(
    clean_path: Path,
    events_path: Path,
    output_dir: Path = REPORTS_DIR,
) -> tuple[Path, Path, Path]:
    logger = get_logger()
    ensure_dir(output_dir)

    clean_df = pd.read_csv(clean_path, parse_dates=["datetime_jst_naive"])
    clean_df["month"] = clean_df["datetime_jst_naive"].dt.strftime("%Y-%m")
    clean_df["timeband"] = clean_df["datetime_jst_naive"].apply(assign_timeband)

    observations = (
        clean_df.groupby(["month", "timeband"])
        .size()
        .rename("T_minutes")
        .reset_index()
    )

    events_df = pd.read_csv(events_path, parse_dates=["detected_at_jst"])
    if not events_df.empty:
        events_df["month"] = events_df["detected_at_jst"].dt.strftime("%Y-%m")
        events_df["timeband"] = events_df["detected_at_jst"].apply(assign_timeband)
        counts = (
            events_df.groupby(["month", "timeband"])
            .size()
            .rename("N_events")
            .reset_index()
        )
    else:
        counts = pd.DataFrame(columns=["month", "timeband", "N_events"])

    merged = observations.merge(counts, on=["month", "timeband"], how="left")
    merged["N_events"] = merged["N_events"].fillna(0).astype(int)
    merged["lambda_per_minute"] = merged["N_events"] / merged["T_minutes"]
    merged["P_at_least_1"] = 1 - np.exp(
        -merged["lambda_per_minute"] * merged["T_minutes"]
    )

    lambda_path = output_dir / "lambda_by_month_timeband.csv"
    prob_path = output_dir / "probability_by_month_timeband.csv"
    summary_path = output_dir / "summary.txt"

    merged[["month", "timeband", "N_events", "T_minutes", "lambda_per_minute"]].to_csv(
        lambda_path, index=False
    )
    merged[["month", "timeband", "P_at_least_1"]].to_csv(prob_path, index=False)

    total_n = merged["N_events"].sum()
    total_t = merged["T_minutes"].sum()
    total_lambda = total_n / total_t if total_t else 0
    total_p = 1 - np.exp(-total_lambda * total_t) if total_t else 0

    timeband_summary = (
        merged.groupby("timeband")
        .agg(N_events=("N_events", "sum"), T_minutes=("T_minutes", "sum"))
        .reset_index()
    )
    timeband_summary["lambda_per_minute"] = (
        timeband_summary["N_events"] / timeband_summary["T_minutes"]
    )

    with summary_path.open("w", encoding="utf-8") as f:
        f.write("Overall Summary\n")
        f.write(f"Total events: {total_n}\n")
        f.write(f"Total minutes: {total_t}\n")
        f.write(f"Lambda per minute: {total_lambda:.6f}\n")
        f.write(f"P(N>=1): {total_p:.6f}\n\n")
        f.write("By Timeband\n")
        for _, row in timeband_summary.iterrows():
            f.write(
                f"{row['timeband']}: N={row['N_events']}, T={row['T_minutes']}, "
                f"lambda={row['lambda_per_minute']:.6f}\n"
            )

    logger.info("Saved reports to %s", output_dir)
    return lambda_path, prob_path, summary_path
