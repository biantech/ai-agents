"""Run PEG-ROIC analysis by stock-list file."""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import unittest

from agent import config, data_sources, pipeline, report, scoring

log = logging.getLogger(__name__)


def run_tests() -> int:
    suite = unittest.TestLoader().discover("tests", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def _checkpoint_path(codes: list[str], prefix: str) -> str:
    identity = "\n".join([prefix, *codes]).encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()[:16]
    return os.path.join(config.CACHE_DIR, f"analysis_{digest}.checkpoint.pkl")


def analyze_and_report(codes: list[str], prefix: str = "", top_n: int = config.TOP_N,
                       restart: bool = False) -> None:
    checkpoint_path = _checkpoint_path(codes, prefix)
    if restart:
        pipeline.clear_checkpoint(checkpoint_path)
    raw = pipeline.analyze_all(codes, checkpoint_path=checkpoint_path)
    ranking = scoring.build_ranking(raw.to_dict("records"))
    preferred = scoring.preferred_targets(ranking)
    top = scoring.top_targets(ranking, top_n)
    report.save_csv(ranking, f"{prefix}PEG-ROIC排名_全样本.csv")
    report.save_csv(preferred, f"{prefix}PEG-ROIC优选池.csv")
    report.save_csv(top, f"{prefix}PEG-ROIC_Top{top_n}.csv")
    path = report.save_markdown(
        report.build_markdown(ranking, preferred, top, top_n),
        f"{prefix}PEG-ROIC复合分析报告.md")
    pipeline.clear_checkpoint(checkpoint_path)
    log.info(
        "Analysis completed: stocks=%d preferred=%d top_candidates=%d report=%s",
        len(ranking), len(preferred), len(top), path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PEG-ROIC composite analysis")
    parser.add_argument("limit", nargs="?", type=int,
                        help="only analyze the first N merged stock codes")
    parser.add_argument("--file", metavar="NAME",
                        help="only analyze one file in the list directory")
    parser.add_argument("--top", type=int, default=config.TOP_N, metavar="N",
                        help=f"maximum candidate count in the report (default: {config.TOP_N})")
    parser.add_argument("--restart", action="store_true",
                        help="discard saved progress and analyze from the beginning")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        parser.error("limit must be greater than 0")
    if args.limit is not None and args.file:
        parser.error("limit and --file cannot be used together")
    if args.top <= 0:
        parser.error("--top must be greater than 0")
    return args


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t", "test"):
        raise SystemExit(run_tests())
    args = parse_args()
    config.ensure_dirs()
    if args.file:
        codes = data_sources.get_codes_from_file(args.file)
        if codes:
            stem = os.path.splitext(os.path.basename(args.file))[0]
            analyze_and_report(codes, f"{stem}_", args.top, args.restart)
        else:
            log.warning("No stock codes found in list file: %s", args.file)
        return
    if args.limit is not None:
        codes = data_sources.get_stock_list()[:args.limit]
        if codes:
            analyze_and_report(codes, top_n=args.top, restart=args.restart)
        else:
            log.warning("No stock codes found in list directory")
        return
    groups = data_sources.get_codes_by_file()
    if not groups:
        log.warning("No stock codes found in list directory")
        return
    for stem, codes in groups:
        analyze_and_report(codes, f"{stem}_", args.top, args.restart)


if __name__ == "__main__":
    main()
