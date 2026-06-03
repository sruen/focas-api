"""CLI for read-only historical experience lookup."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .report import query_experience


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOCAS 赛前历史经验调用")
    subparsers = parser.add_subparsers(dest="command", required=True)
    query = subparsers.add_parser("query", help="按赛前 fingerprint 查询历史经验")
    query.add_argument("--fingerprint", required=True, type=Path)
    query.add_argument("--out", type=Path, default=Path("experience_report.json"))
    args = parser.parse_args(argv)
    report = query_experience(args.fingerprint, args.out)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
