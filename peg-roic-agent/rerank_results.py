"""Rerank an existing PEG-ROIC CSV without recalculating source data."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


SORT_COLUMNS = ["composite_score", "roic_wacc_spread", "peg_rank_value"]


def default_output_path(input_path: Path, top_n: int) -> Path:
    stem = re.sub(r"Top\d+$", f"Top{top_n}", input_path.stem)
    if stem == input_path.stem:
        stem = f"{stem}_Top{top_n}"
    return input_path.with_name(f"{stem}{input_path.suffix}")


def rerank_results(input_path: Path, top_n: int, output_path: Path | None = None) -> Path:
    frame = pd.read_csv(input_path, dtype={"code": str})
    missing = [column for column in SORT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    result = frame.sort_values(
        SORT_COLUMNS,
        ascending=[False, False, True],
        na_position="last",
        kind="stable",
    ).head(top_n).copy()
    result["排名"] = range(1, len(result) + 1)

    target = output_path or default_output_path(input_path, top_n)
    result.to_csv(target, index=False, encoding="utf-8-sig")
    return target


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rerank an existing PEG-ROIC CSV without recalculating data")
    parser.add_argument("input", type=Path, help="existing PEG-ROIC CSV file")
    parser.add_argument("--top", type=int, default=30, metavar="N",
                        help="number of rows to output (default: 30)")
    parser.add_argument("--output", type=Path,
                        help="output CSV path (default: derived from the input name)")
    args = parser.parse_args(argv)
    if args.top <= 0:
        parser.error("--top must be greater than 0")
    return args


def main() -> None:
    args = parse_args()
    try:
        target = rerank_results(args.input, args.top, args.output)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from error
    print(target)


if __name__ == "__main__":
    main()
