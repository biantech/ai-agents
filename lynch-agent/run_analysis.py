# -*- coding: utf-8 -*-
"""Entry point: run the Peter-Lynch PEG analysis over the files in list/.

Usage:
    python3 run_analysis.py            # per-file mode: one report set per file
    python3 run_analysis.py 5          # quick smoke test on first 5 merged codes
    python3 run_analysis.py stocks.csv # analyze only list/stocks.csv
    python3 run_analysis.py list/stocks.csv
    python3 run_analysis.py --test     # run the unit-test suite (regression)

In the default (no-arg) mode each file under list/ is analysed in isolation and
produces its own prefixed outputs (e.g. xiaofei.txt -> xiaofei_林奇PEG分析报告.md).
The numeric-limit smoke path keeps the legacy behaviour: it merges all codes,
takes the first N, and writes a single un-prefixed report for quick debugging.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import unittest

from agent import config, pipeline, portfolio, report
from agent import data_sources as ds

log = logging.getLogger(__name__)


def run_tests() -> int:
    """Discover and run the unit-test suite; return process exit code."""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def _analyze_and_report(codes: list[str], prefix: str = "",
                        provided_names: dict[str, str] | None = None,
                        restart: bool = False) -> None:
    """Run the full analysis on ``codes`` and persist a prefixed report set.

    ``prefix`` is prepended to every output filename (empty string = legacy
    un-prefixed names). Ranking / attractive filter / portfolio are all computed
    solely from ``codes``, so per-file calls stay fully isolated.
    """
    checkpoint_path = _checkpoint_path(codes, prefix)
    if restart:
        pipeline.clear_checkpoint(checkpoint_path)
    df = pipeline.analyze_all(
        codes,
        provided_names=provided_names,
        checkpoint_path=checkpoint_path,
    )

    # Step 6 ranking + attractive filter.
    ranking = portfolio.build_ranking(df.to_dict("records"))
    attractive = portfolio.attractive_targets(ranking)

    # Step 7 Top-10 portfolio.
    top, buckets = portfolio.build_portfolio(ranking)

    # Persist outputs (prefixed per source file when prefix is given).
    report.save_csv(ranking, f"{prefix}PEG排名表_全样本.csv")
    if not attractive.empty:
        report.save_csv(attractive, f"{prefix}PEG小于1_吸引标的.csv")
    if not top.empty:
        report.save_csv(top, f"{prefix}Top10组合配置.csv")

    md = report.build_markdown(ranking, attractive, top, buckets)
    md_path = report.save_markdown(md, f"{prefix}林奇PEG分析报告.md")
    pipeline.clear_checkpoint(checkpoint_path)

    log.info("Analysis completed")
    log.info("Ranked stocks: %d", len(ranking))
    log.info("PEG below 1: %d", len(attractive))
    log.info("Portfolio: %d names", len(top))
    log.info("Report: %s", md_path)


def _checkpoint_path(codes: list[str], prefix: str) -> str:
    """Return a stable checkpoint path for one input group."""
    identity = "\n".join([prefix, *codes]).encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()[:16]
    return os.path.join(config.CACHE_DIR, f"analysis_{digest}.checkpoint.pkl")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse an optional numeric limit or a specific list filename."""
    parser = argparse.ArgumentParser(description="Peter Lynch PEG analysis")
    parser.add_argument(
        "target", nargs="?", help="stock limit, filename, or list/filename",
    )
    parser.add_argument(
        "--restart", action="store_true",
        help="discard saved progress and analyze from the beginning",
    )
    args = parser.parse_args(argv)
    if args.target and args.target.isdigit() and int(args.target) <= 0:
        parser.error("limit must be greater than 0")
    return args


def _codes_and_names(stocks: list[tuple[str, str]]) -> tuple[list[str], dict[str, str]]:
    """Split parsed stock entries into pipeline arguments."""
    codes = [code for code, _ in stocks]
    names = {code: name for code, name in stocks if name}
    return codes, names


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Regression entry: run unit tests instead of the full pipeline.
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t", "test"):
        sys.exit(run_tests())

    args = parse_args()
    config.ensure_dirs()

    # Smoke-test path: numeric limit -> merge all codes, take first N, single
    # un-prefixed report (legacy behaviour, kept for quick debugging).
    if args.target and args.target.isdigit():
        limit = int(args.target)
        codes, names = _codes_and_names(ds.get_stock_entries()[:limit])
        if not codes:
            log.warning("No stock codes found in list directory")
            return
        log.info("Analyzing %d stocks with the Peter Lynch PEG framework", len(codes))
        _analyze_and_report(codes, provided_names=names, restart=args.restart)
        return

    if args.target:
        codes, names = _codes_and_names(ds.get_stocks_from_file(args.target))
        if not codes:
            log.warning("No stock codes found in list file: %s", args.target)
            return
        stem = os.path.splitext(os.path.basename(args.target))[0]
        log.info("Analyzing %d stocks from %s", len(codes), args.target)
        _analyze_and_report(
            codes, prefix=f"{stem}_", provided_names=names,
            restart=args.restart,
        )
        return

    # Default path: one isolated report set per file under list/.
    groups = ds.get_stocks_by_file()
    if not groups:
        log.warning("No stock codes found in list directory")
        return

    total = len(groups)
    log.info("Found %d list files; generating one report set per file", total)
    for i, (stem, stocks) in enumerate(groups, 1):
        codes, names = _codes_and_names(stocks)
        log.info("[%d/%d] file: %s (%d stocks)", i, total, stem, len(codes))
        _analyze_and_report(
            codes, prefix=f"{stem}_", provided_names=names,
            restart=args.restart,
        )


if __name__ == "__main__":
    main()
