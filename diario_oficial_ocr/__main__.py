from __future__ import annotations

import argparse
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from diario_oficial_ocr.config import DateRange, load_config, split_date_range
from diario_oficial_ocr.logging_utils import configure_logging
from diario_oficial_ocr.reporting import export_results
from diario_oficial_ocr.runner import Runner
from diario_oficial_ocr.utils import iter_dates

logger = logging.getLogger(__name__)


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _run_range(range_spec: DateRange) -> None:
    config = load_config()
    runner = Runner(config)
    runner.run_dates(iter_dates(range_spec.start, range_spec.end))


def main() -> None:
    parser = argparse.ArgumentParser(prog="diario_oficial_ocr")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run OCR extraction")
    run_parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    run_parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")

    args = parser.parse_args()
    if args.command != "run":
        parser.print_help()
        return

    configure_logging()
    config = load_config()
    date_range = DateRange(start=_parse_date(args.start), end=_parse_date(args.end))
    ranges = split_date_range(date_range, config.workers)

    if config.workers > 1:
        with ProcessPoolExecutor(max_workers=config.workers) as executor:
            futures = [executor.submit(_run_range, r) for r in ranges]
            for future in as_completed(futures):
                future.result()
    else:
        _run_range(date_range)

    export_results(Runner(config).db, config.storage.output_dir)


if __name__ == "__main__":
    main()
