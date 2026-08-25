#!/usr/bin/env python3
"""Convert a legacy .xls file to .csv format, or extract selected columns."""
import csv
import logging
import os
import sys

import xlrd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _cell_value(sheet, book, row_idx, col_idx):
    """Read a cell and normalize date/integer values for CSV output."""
    cell = sheet.cell(row_idx, col_idx)
    value = cell.value
    # Convert Excel date cells to readable datetime strings
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            value = xlrd.xldate.xldate_as_datetime(
                value, book.datemode
            ).isoformat(sep=" ")
        except Exception:
            pass
    # Drop trailing .0 for integer-valued floats
    elif cell.ctype == xlrd.XL_CELL_NUMBER and value == int(value):
        value = int(value)
    return value


def extract_columns(xls_path, columns, out_path=None):
    """Extract the given columns (1-based) from an .xls into a csv.

    columns is a list of 1-based column numbers, output in the given order.
    Multi-sheet files output one csv per sheet.
    """
    if not os.path.isfile(xls_path):
        raise FileNotFoundError(f"input file not found: {xls_path}")
    if not columns:
        raise ValueError("at least one column is required")
    for column in columns:
        if column < 1:
            raise ValueError(f"column must be >= 1, got {column}")

    book = xlrd.open_workbook(xls_path)
    base, _ = os.path.splitext(xls_path)
    col_indexes = [c - 1 for c in columns]
    suffix = "col" + "_".join(str(c) for c in columns)
    outputs = []

    for idx in range(book.nsheets):
        sheet = book.sheet_by_index(idx)
        missing = [c for c in columns if c - 1 >= sheet.ncols]
        if missing:
            log.warning(
                "sheet '%s' skipped: only %d columns, missing %s",
                sheet.name, sheet.ncols, missing,
            )
            continue

        if book.nsheets == 1:
            target = out_path or f"{base}_{suffix}.csv"
        else:
            target = f"{base}_{sheet.name}_{suffix}.csv"

        with open(target, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            for row_idx in range(sheet.nrows):
                writer.writerow([
                    _cell_value(sheet, book, row_idx, col_idx)
                    for col_idx in col_indexes
                ])

        outputs.append(target)
        log.info(
            "sheet '%s' cols %s -> %s (%d rows)",
            sheet.name, columns, target, sheet.nrows,
        )

    return outputs


def xls_to_csv(xls_path, csv_path=None):
    """Convert an .xls file to .csv. Multi-sheet files output one csv per sheet."""
    if not os.path.isfile(xls_path):
        raise FileNotFoundError(f"input file not found: {xls_path}")

    book = xlrd.open_workbook(xls_path)
    base, _ = os.path.splitext(xls_path)
    outputs = []

    for idx in range(book.nsheets):
        sheet = book.sheet_by_index(idx)
        if book.nsheets == 1:
            out_path = csv_path or (base + ".csv")
        else:
            out_path = f"{base}_{sheet.name}.csv"

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            for row_idx in range(sheet.nrows):
                row = [
                    _cell_value(sheet, book, row_idx, col_idx)
                    for col_idx in range(sheet.ncols)
                ]
                writer.writerow(row)

        outputs.append(out_path)
        log.info("sheet '%s' -> %s (%d rows)", sheet.name, out_path, sheet.nrows)

    return outputs


def _parse_columns(spec):
    """Parse a column spec like '1,5,6' into a list of ints [1, 5, 6]."""
    columns = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        columns.append(int(part))
    if not columns:
        raise SystemExit("error: -c/--column requires at least one column number")
    return columns


def main(argv):
    """CLI. Usage:
      xls_to_csv.py <input.xls> [output.csv]           # full conversion
      xls_to_csv.py <input.xls> -c N[,N...] [out.csv]  # extract columns (1-based)
    """
    args = argv[1:]
    src = args[0] if args else os.path.expanduser("~/Downloads/H30097cons.xls")
    rest = args[1:]

    columns = None
    if rest and rest[0] in ("-c", "--column"):
        if len(rest) < 2:
            raise SystemExit("error: -c/--column requires a column spec, e.g. 1,5,6")
        columns = _parse_columns(rest[1])
        rest = rest[2:]

    dst = rest[0] if rest else None
    if columns is not None:
        extract_columns(src, columns, dst)
    else:
        xls_to_csv(src, dst)


if __name__ == "__main__":
    main(sys.argv)
