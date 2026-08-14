from __future__ import annotations
import argparse, logging, sys
from agent import data_sources, pipeline, report

def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate one investment report per stock code")
    parser.add_argument("--list", dest="list_path", default=data_sources.config.LIST_PATH)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offline", action="store_true", help="only render reports with unavailable data placeholders")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    codes = data_sources.read_codes(args.list_path)
    if args.limit: codes = codes[:args.limit]
    if not codes: logging.warning("No stock codes found"); return 0
    records = ({"code": code, "name": "待补充"} for code in codes) if args.offline else pipeline.analyze_all(codes)
    for item in records: logging.info("Report saved: %s", report.save(item))
    return 0

if __name__ == "__main__": sys.exit(main())
