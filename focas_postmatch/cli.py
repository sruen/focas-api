"""CLI for isolated FOCAS post-match review and storage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from shared.postmatch_schema import PostmatchSample

from .analyzer import promotion_check, summary
from .review import review_files
from .store import add_sample, find_similar, list_samples, rebuild_index


def _print(value: Any) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOCAS 赛后复盘与事实样本入库")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="从赛前快照与赛果生成事实样本")
    review.add_argument("--prematch", required=True, type=Path)
    review.add_argument("--result", required=True, type=Path)
    review.add_argument("--out", required=True, type=Path)

    add = subparsers.add_parser("add", help="写入事实样本库")
    add.add_argument("--file", required=True, type=Path)

    subparsers.add_parser("rebuild-index", help="重建赛后样本索引")
    subparsers.add_parser("summary", help="查看赛后样本统计")

    validate = subparsers.add_parser("validate", help="校验 v0.2 赛后事实样本")
    validate.add_argument("--file", required=True, type=Path)

    similar = subparsers.add_parser("similar", help="查询相似样本")
    similar.add_argument("--key", required=True)

    promotion = subparsers.add_parser("promotion", help="严格升级检查")
    promotion.add_argument("--key", required=True)

    listing = subparsers.add_parser("list", help="列出最近样本")
    listing.add_argument("--limit", type=int, default=50)

    args = parser.parse_args(argv)
    if args.command == "review":
        sample = review_files(args.prematch, args.result, args.out)
        _print({"success": True, "out": str(args.out), "match_id": sample.match_id})
    elif args.command == "add":
        sample_id = add_sample(PostmatchSample.from_dict(_read_json(args.file)))
        _print({"sample_id": sample_id})
    elif args.command == "rebuild-index":
        index = rebuild_index()
        _print({"success": True, "total_samples": index["total_samples"]})
    elif args.command == "summary":
        _print(summary())
    elif args.command == "validate":
        try:
            sample = PostmatchSample.from_dict(_read_json(args.file))
            sample.validate()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _print({"valid": False, "error": str(exc)})
            return 1
        _print({"valid": True})
    elif args.command == "similar":
        _print([sample.to_dict() for sample in find_similar(args.key)])
    elif args.command == "promotion":
        _print(promotion_check(args.key))
    elif args.command == "list":
        _print([sample.to_dict() for sample in list_samples(args.limit)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
