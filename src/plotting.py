from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .config import REPORTS_DIR
from .utils import ensure_dir, get_logger


def plot_heatmaps(
    lambda_csv: Path,
    prob_csv: Path,
    output_dir: Path = REPORTS_DIR,
) -> tuple[Path, Path]:
    logger = get_logger()
    ensure_dir(output_dir)

    lambda_df = pd.read_csv(lambda_csv)
    prob_df = pd.read_csv(prob_csv)

    lambda_pivot = lambda_df.pivot(index="month", columns="timeband", values="lambda_per_minute")
    prob_pivot = prob_df.pivot(index="month", columns="timeband", values="P_at_least_1")

    lambda_path = output_dir / "lambda_heatmap.png"
    prob_path = output_dir / "probability_heatmap.png"

    _plot_heatmap(lambda_pivot, "Lambda per minute", lambda_path)
    _plot_heatmap(prob_pivot, "P(N>=1)", prob_path)

    logger.info("Saved heatmaps to %s", output_dir)
    return lambda_path, prob_path


def _plot_heatmap(data: pd.DataFrame, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    cax = ax.imshow(data.fillna(0), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(data.columns)))
    ax.set_xticklabels(data.columns)
    ax.set_yticks(range(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_title(title)
    fig.colorbar(cax, ax=ax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
