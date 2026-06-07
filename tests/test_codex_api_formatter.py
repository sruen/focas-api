from focas_engine.codex_api_formatter import (
    build_user_message_from_rows,
    format_odds_package,
    validate_fundamentals,
)


def _row(company: str, role: str, snapshot: str, h: float, d: float, a: float) -> dict:
    return {
        "赛事类型": "友谊赛",
        "日期": "2026-06-07",
        "赛季": "2026",
        "联赛": "国际友谊赛",
        "主队": "主队",
        "客队": "客队",
        "公司": company,
        "公司角色": role,
        "快照类型": snapshot,
        "主胜赔率": h,
        "平局赔率": d,
        "客胜赔率": a,
        "返还率": 94.0,
        "体系": "94系",
        "体系标注": "test",
        "源字段": "test",
    }


def test_validate_fundamentals_lists_missing_fields():
    text = "比赛：A vs B\n赛事：友谊赛\n中立场：否\n"
    missing = validate_fundamentals(text)
    assert "主队档位：" in missing
    assert "客队档位：" in missing
    assert "分布类型：" in missing


def test_format_odds_package_keeps_company_snapshots_separate():
    rows = [
        _row("William", "core", "initial", 1.8, 3.6, 4.5),
        _row("William", "core", "current", 1.75, 3.75, 4.8),
        _row("Ladbrokes", "core", "initial", 1.85, 3.5, 4.2),
        _row("Ladbrokes", "core", "current", 1.9, 3.4, 4.0),
        _row("BetVictor", "auxiliary", "current", 1.78, 3.55, 4.6),
    ]
    text = format_odds_package(rows)
    assert "公司：William Hill\n初赔：主胜 1.80 / 平局 3.60 / 客胜 4.50\n收盘：主胜 1.75 / 平局 3.75 / 客胜 4.80" in text
    assert "公司：Ladbrokes\n初赔：主胜 1.85 / 平局 3.50 / 客胜 4.20\n收盘：主胜 1.90 / 平局 3.40 / 客胜 4.00" in text
    assert "公司：BetVictor（辅助）\n初赔：不可用\n收盘：主胜 1.78 / 平局 3.55 / 客胜 4.60" in text
    assert "N/A" not in text


def test_build_user_message_from_rows_validates_required_fields():
    fundamentals = "\n".join([
        "比赛：A vs B",
        "赛事：友谊赛",
        "中立场：否",
        "主队档位：中强",
        "客队档位：中上",
        "分布类型：缓冲分布",
    ])
    message = build_user_message_from_rows(
        fundamentals,
        [_row("William", "core", "initial", 1.8, 3.6, 4.5)],
    )
    assert message.startswith("[FOCAS分析]")
    assert "基本面模板：" in message
    assert "赔率包：" in message
    assert "公司：William Hill" in message
