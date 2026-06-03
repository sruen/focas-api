"""CLI for isolated FOCAS pre-match analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .snapshot import analyze_match_package


def _print(value: object) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOCAS 赛前分析")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="分析比赛包并输出赛前快照")
    analyze.add_argument("--match-package", required=True, type=Path)
    analyze.add_argument("--out", required=True, type=Path)
    analyze.add_argument("--fingerprint-out", type=Path)
    analyze.add_argument("--experience-out", type=Path, default=Path("experience_report.json"))
    analyze.add_argument("--with-experience", action="store_true")
    analyze.add_argument("--table", type=Path)
    args = parser.parse_args(argv)
    snapshot = analyze_match_package(
        args.match_package,
        out=args.out,
        fingerprint_out=args.fingerprint_out,
        experience_out=args.experience_out,
        with_experience=args.with_experience,
        table_path=args.table,
    )
    response = {"success": True, "match_id": snapshot.match_id, "out": str(args.out)}
    if args.with_experience:
        experience = json.loads(args.experience_out.read_text(encoding="utf-8"))
        response.update(
            {
                "experience_out": str(args.experience_out),
                "experience_level": experience["experience_level"],
                "usable_for_mainline": experience["usable_for_mainline"],
            }
        )
    _print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
