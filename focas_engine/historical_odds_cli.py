from __future__ import annotations

import argparse
from pathlib import Path

from .match_package_loader import load_package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="focas-export-odds-csv",
        description="Export normalized historical odds snapshot rows from a FOCAS match package.",
    )
    parser.add_argument("package", help="Path to the match package .zip")
    parser.add_argument("output", help="Path to write the normalized historical odds CSV")
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print package-loader diagnostics after export.",
    )
    args = parser.parse_args(argv)

    result = load_package(Path(args.package))
    result.write_historical_odds_csv(Path(args.output))
    print(f"wrote {len(result.historical_odds_rows)} rows to {args.output}")
    if args.diagnostics:
        for item in result.diagnostics:
            location = f" [{item.file}]" if item.file else ""
            print(f"{item.level}{location}: {item.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
