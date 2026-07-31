# -*- coding: utf-8 -*-
"""Entry point: run the Peter-Lynch PEG analysis over the files in list/.

Usage:
    python3 run_analysis.py            # per-file mode: one report set per file
    python3 run_analysis.py 5          # quick smoke test on first 5 merged codes
    python3 run_analysis.py --test     # run the unit-test suite (regression)

In the default (no-arg) mode each file under list/ is analysed in isolation and
produces its own prefixed outputs (e.g. xiaofei.txt -> xiaofei_林奇PEG分析报告.md).
The numeric-limit smoke path keeps the legacy behaviour: it merges all codes,
takes the first N, and writes a single un-prefixed report for quick debugging.
"""
from __future__ import annotations

import sys
import unittest

from agent import config, pipeline, portfolio, report
from agent import data_sources as ds


def run_tests() -> int:
    """Discover and run the unit-test suite; return process exit code."""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def _analyze_and_report(codes: list[str], prefix: str = "") -> None:
    """Run the full analysis on ``codes`` and persist a prefixed report set.

    ``prefix`` is prepended to every output filename (empty string = legacy
    un-prefixed names). Ranking / attractive filter / portfolio are all computed
    solely from ``codes``, so per-file calls stay fully isolated.
    """
    df = pipeline.analyze_all(codes)

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

    print("\n=== Done ===")
    print(f"Ranked stocks : {len(ranking)}")
    print(f"PEG < 1       : {len(attractive)}")
    print(f"Portfolio     : {len(top)} names")
    print(f"Report        : {md_path}")


def main() -> None:
    # Regression entry: run unit tests instead of the full pipeline.
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t", "test"):
        sys.exit(run_tests())

    config.ensure_dirs()

    # Smoke-test path: numeric limit -> merge all codes, take first N, single
    # un-prefixed report (legacy behaviour, kept for quick debugging).
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            limit = None
        if limit is not None:
            codes = ds.get_stock_list()[:limit]
            if not codes:
                print("No stock codes found in list/ directory")
                return
            print(f"Analyzing {len(codes)} stocks (Peter Lynch PEG framework)...")
            _analyze_and_report(codes)
            return

    # Default path: one isolated report set per file under list/.
    groups = ds.get_codes_by_file()
    if not groups:
        print("No stock codes found in list/ directory")
        return

    total = len(groups)
    print(f"Found {total} file(s) in list/; generating one report set per file.")
    for i, (stem, codes) in enumerate(groups, 1):
        print(f"\n===== [{i}/{total}] file: {stem} ({len(codes)} stocks) =====")
        _analyze_and_report(codes, prefix=f"{stem}_")


if __name__ == "__main__":
    main()
