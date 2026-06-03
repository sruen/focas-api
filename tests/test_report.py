from pathlib import Path

from focas_engine.io import load_input
from focas_engine.pipeline import FocasPipeline
from focas_engine.report import render_frontend_report


def _run(example: str, table_path: str):
    match, strength, pulls, mode, odds = load_input(Path("examples") / example)
    result = FocasPipeline(table_path=table_path).run(
        match=match,
        strength=strength,
        pulls=pulls,
        book_mode=mode,
        odds=odds,
    )
    text = render_frontend_report(
        match=match,
        strength=strength,
        pulls=pulls,
        book_mode=mode,
        odds=odds,
        result=result,
    )
    return result, text


def test_report_renders_stop_only_for_basic_gate(mini_table):
    result, text = _run("basic_gate_stop_case.json", mini_table)
    assert result.report_mode == "STOP_REPORT_ONLY"
    assert "Basic_Context_Status = INCOMPLETE" in text
    assert "Odds_Analysis = FORBIDDEN" in text
    assert "Mainline_Output = FORBIDDEN" in text
    for blocked in ("## 1. 先说人话", "主队=普强", "本场原书模式", "最终结构方向"):
        assert blocked not in text


def test_report_renders_stop_only_for_table_gate():
    result, text = _run("table_gate_stop_case.json", "missing_table.xlsx")
    assert result.report_mode == "STOP_REPORT_ONLY"
    assert "TABLE_READ_CONFIRMED = NO" in text
    assert "Mainline_Output = FORBIDDEN" in text
    assert "## 14. 最终结构方向" not in text


def test_frontend_report_is_natural_language_with_lookup_evidence(mini_table):
    result, text = _run("valid_complete_match_input.json", mini_table)
    assert result.stop is False
    assert "## 1. 先说人话" in text
    assert "## 10. 现代骨架区间查表" in text
    assert "【硬判断公司】William / Ladbrokes" in text
    assert "【市场背景】Avg" in text
    assert "lookup_status" in text
    assert "- 本场原书模式：None" not in text
    for hidden in ("Stage 9", "Stage 10", "Mainline_Output", "Basic_Context_Status"):
        assert hidden not in text


def test_backend_audit_exposes_backend_status_only_when_enabled(mini_table):
    match, strength, pulls, mode, odds = load_input(Path("examples") / "valid_complete_match_input.json")
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    normal = render_frontend_report(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds, result=result
    )
    audit = render_frontend_report(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds, result=result, backend_audit=True
    )
    assert "Mainline_Output" not in normal
    assert "Mainline_Output=PASS" in audit
