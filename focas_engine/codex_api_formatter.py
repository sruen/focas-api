from __future__ import annotations

from collections import defaultdict
from typing import Any


REQUIRED_FUNDAMENTAL_FIELDS = [
    "比赛：",
    "赛事：",
    "中立场：",
    "主队档位：",
    "客队档位：",
    "分布类型：",
]

COMPANY_OUTPUT_ORDER = ["William", "Ladbrokes", "BetVictor", "Avg"]


def validate_fundamentals(text: str) -> list[str]:
    """Return missing required fields before handing work to the analysis layer."""
    content = text or ""
    return [field for field in REQUIRED_FUNDAMENTAL_FIELDS if field not in content]


def _odds_line(label: str, row: dict[str, Any] | None) -> str:
    if row is None:
        return f"{label}：不可用"
    return (
        f"{label}：主胜 {float(row['主胜赔率']):.2f} / "
        f"平局 {float(row['平局赔率']):.2f} / "
        f"客胜 {float(row['客胜赔率']):.2f}"
    )


def _company_display_name(company: str, role: str) -> str:
    if company == "William":
        return "William Hill"
    if company == "BetVictor" and role == "auxiliary":
        return "BetVictor（辅助）"
    if company == "Avg":
        return "Avg（辅助）"
    return company


def format_odds_package(rows: list[dict[str, Any]]) -> str:
    """Build the fixed v1.3 odds package text without mixing company snapshots."""
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    roles: dict[str, str] = {}
    for row in rows:
        company = str(row.get("公司") or "").strip()
        snapshot = str(row.get("快照类型") or "").strip()
        if company not in COMPANY_OUTPUT_ORDER or snapshot not in {"initial", "current"}:
            continue
        grouped[company][snapshot] = row
        roles[company] = str(row.get("公司角色") or "")

    blocks: list[str] = []
    for company in COMPANY_OUTPUT_ORDER:
        snapshots = grouped.get(company)
        if not snapshots:
            continue
        display = _company_display_name(company, roles.get(company, ""))
        block = [
            f"公司：{display}",
            _odds_line("初赔", snapshots.get("initial")),
            _odds_line("收盘", snapshots.get("current")),
        ]
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def build_user_message(fundamentals: str, odds_package: str) -> str:
    return f"""[FOCAS分析]

基本面模板：
{fundamentals}

赔率包：
{odds_package}"""


def build_user_message_from_rows(fundamentals: str, rows: list[dict[str, Any]]) -> str:
    missing = validate_fundamentals(fundamentals)
    if missing:
        raise ValueError(f"fundamentals missing required fields: {', '.join(missing)}")
    return build_user_message(fundamentals, format_odds_package(rows))
