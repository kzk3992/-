from __future__ import annotations

import json
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import yaml

from backtest_core import Summary, Trade, simulate_strategy
from data_loader import MarketData, load_all_timeframes
from indicators import compute_indicators
from strategy_bits import StrategyConstraints, iter_strategy_ids, validate_strategy

logger = logging.getLogger(__name__)


def _load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _flatten_summary(summary: Summary, timeframe: str, bit_count: int) -> dict:
    bits = format(summary.strategy_id, f"0{bit_count}b")
    return {
        "timeframe": timeframe,
        "strategy_id": summary.strategy_id,
        "strategy_bits": bits,
        "total_trades": summary.total_trades,
        "win_rate_total": summary.win_rate_total,
        "pips_total": summary.pips_total,
        "avg_pips_per_trade": summary.avg_pips_per_trade,
        "max_dd_pips": summary.max_dd_pips,
        "max_consecutive_losses": summary.max_consecutive_losses,
        "monthly_pips_avg": summary.monthly_pips_avg,
        "monthly_pips_std": summary.monthly_pips_std,
        "compound_return_pct": summary.compound_return_pct,
        "max_dd_pct": summary.max_dd_pct,
        "stopped_reason": summary.stopped_reason,
    }


def _worker(
    strategy_ids: Iterable[int],
    market: MarketData,
    indicators: Dict[str, np.ndarray],
    config: dict,
    constraints: StrategyConstraints,
    export_trades: bool,
    export_ids: set[int],
) -> Tuple[List[Summary], Dict[int, List[Trade]]]:
    summaries: List[Summary] = []
    trades: Dict[int, List[Trade]] = {}
    bt_config = {
        "initial_equity": config["backtest"]["initial_equity"],
        "risk_per_trade": config["backtest"]["risk_per_trade"],
        "pip_size": config["backtest"]["pip_size"],
        "spread_pips": config["backtest"]["spread_pips"],
        "fee_per_trade": config["backtest"]["fee_per_trade"],
        "max_dd_pct_stop": config["backtest"]["max_dd_pct_stop"],
        "early_stop_enabled": config["backtest"]["early_stop"]["enabled"],
        "early_stop_min_trades": config["backtest"]["early_stop"]["min_trades"],
        "early_stop_max_losses": config["backtest"]["early_stop"]["max_consecutive_losses"],
    }
    for strategy_id in strategy_ids:
        if not validate_strategy(strategy_id, constraints):
            continue
        summary, trade_log = simulate_strategy(
            strategy_id,
            market.time,
            market.open,
            market.high,
            market.low,
            market.close,
            indicators,
            bt_config,
            export_trades=export_trades and strategy_id in export_ids,
        )
        summaries.append(summary)
        if trade_log:
            trades[strategy_id] = trade_log
    return summaries, trades


def _chunked(iterable: Iterable[int], size: int) -> Iterable[List[int]]:
    chunk: List[int] = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _write_summary_csv(path: Path, rows: List[dict]) -> None:
    import csv

    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_trades_csv(path: Path, trades: List[Trade]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(trades[0]).keys()))
        writer.writeheader()
        for trade in trades:
            writer.writerow(asdict(trade))


def _save_checkpoint(path: Path, last_strategy_id: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"last_strategy_id": last_strategy_id}, handle)


def _load_checkpoint(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle).get("last_strategy_id")


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = _load_config(Path("config.yaml"))
    output_dir = Path(config["project"]["output_dir"])

    data_cfg = config["data"]
    data = load_all_timeframes(
        Path(data_cfg["base_dir"]),
        data_cfg["timeframes"],
        data_cfg["file_pattern"],
        data_cfg["time_column"],
    )

    bit_count = int(config["strategy"]["bit_count"])
    constraints = StrategyConstraints(**config["strategy"]["constraints"])

    explore_cfg = config["explore"]
    start_id = int(explore_cfg["start_id"])
    end_id = explore_cfg["end_id"]
    chunk_size = int(explore_cfg["chunk_size"])
    workers = int(explore_cfg["workers"])
    rotation = int(explore_cfg["summary_rotation"])

    checkpoint_path = Path(config["project"]["checkpoint_path"])
    last_checkpoint = _load_checkpoint(checkpoint_path)
    if last_checkpoint is not None and last_checkpoint >= start_id:
        start_id = last_checkpoint + 1

    export_cfg = config["export_trades"]
    export_enabled = bool(export_cfg["enabled"])
    export_ids = set(export_cfg["strategy_ids"])

    for timeframe, market in data.items():
        indicators = compute_indicators(market.close, market.high, market.low)
        max_id = end_id if end_id is not None else 2**bit_count
        strategy_ids = iter_strategy_ids(start_id, max_id)

        summary_rows: List[dict] = []
        part_index = 1

        executor_workers = workers or None
        with ProcessPoolExecutor(max_workers=executor_workers) as executor:
            futures = []
            for chunk in _chunked(strategy_ids, chunk_size):
                futures.append(
                    executor.submit(
                        _worker,
                        chunk,
                        market,
                        indicators,
                        config,
                        constraints,
                        export_enabled,
                        export_ids,
                    )
                )

            processed = 0
            for future in futures:
                summaries, trade_logs = future.result()
                for summary in summaries:
                    summary_rows.append(_flatten_summary(summary, timeframe, bit_count))
                    processed += 1
                    if processed % rotation == 0:
                        filename = f"summary_{timeframe}_part{part_index:06d}.csv"
                        _write_summary_csv(output_dir / filename, summary_rows)
                        summary_rows = []
                        part_index += 1
                if trade_logs:
                    for strategy_id, trades in trade_logs.items():
                        trade_path = output_dir / f"trades_{timeframe}_strategy_{strategy_id}.csv"
                        _write_trades_csv(trade_path, trades)
                if summaries:
                    _save_checkpoint(checkpoint_path, summaries[-1].strategy_id)

                if processed % config["project"]["log_every"] == 0:
                    logger.info("Processed %s strategies", processed)

        if summary_rows:
            filename = f"summary_{timeframe}_part{part_index:06d}.csv"
            _write_summary_csv(output_dir / filename, summary_rows)


if __name__ == "__main__":
    run()
