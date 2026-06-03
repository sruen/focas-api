from pathlib import Path

from focas_engine.expected_interval import audit_opening_interval, expected_interval_from_table
from focas_engine.io import load_input
from focas_engine.models import StrengthContext
from focas_engine.pipeline import FocasPipeline
from focas_engine.report import render_frontend_report


def _load(example: str):
    return load_input(Path("examples") / example)


def _run(example: str, table_path: str):
    match, strength, pulls, mode, odds = _load(example)
    result = FocasPipeline(table_path=table_path).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    return match, strength, pulls, mode, odds, result


def test_legacy_narrative_input_returns_formal_pass_with_observation_lean(mini_table):
    *_, result = _run("valid_complete_match_input.json", mini_table)
    assert result.stop is False
    assert result.basic_context_status == "COMPLETE"
    assert result.table_read_confirmed == "YES"
    assert result.strength_source == "USER_PROVIDED"
    assert result.interval_audit.expected.expected_interval_source == "STRENGTH_INTERVAL_BRIDGE"
    assert result.final_direction == "PASS"
    assert result.decision_status == "OBSERVE"
    assert result.structural_lean in {"主胜", "平局", "客胜"}
    assert result.mainline_output_status == "PASS"


def test_auto_estimated_strength_is_labeled_in_frontend(mini_table):
    match, _, pulls, mode, odds = _load("valid_complete_match_input.json")
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=StrengthContext(), pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is False
    assert result.strength_source == "AUTO_ESTIMATED"
    text = render_frontend_report(
        match=match, strength=StrengthContext(), pulls=pulls, book_mode=mode, odds=odds, result=result
    )
    assert "广义实力为辅助估算，不替代人工校准" in text


def test_manual_review_required_strength_stops_mainline(mini_table):
    match, _, pulls, mode, odds = _load("valid_complete_match_input.json")
    match.home.rank = "排名信息无法解析"
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=StrengthContext(), pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is True
    assert result.strength_source == "MANUAL_REVIEW_REQUIRED"
    assert result.mainline_output_status == "FORBIDDEN"
    assert result.report_mode == "STOP_REPORT_ONLY"


def test_p4_missing_table_key_requires_review():
    strength = StrengthContext(
        home_grade="人强",
        away_grade="下游",
        static_gap="主队高4.5档",
        dynamic_adjustment="人工校准",
        final_gap="主队高4.5档",
    )
    expected = expected_interval_from_table(strength=strength)
    assert expected.expected_interval_source == "REVIEW_REQUIRED"
    assert expected.lookup_key_status == "NO_TABLE_MATCH"


def test_rule_fallback_cannot_unlock_formal_interval(tmp_path):
    strength = StrengthContext(
        home_grade="中上",
        away_grade="中游",
        static_gap="主队高一档",
        dynamic_adjustment="人工校准",
        final_gap="主队高一档",
    )
    audit = audit_opening_interval(
        strength=strength,
        estimate=None,
        odds_coordinates=None,
        bridge_path=tmp_path / "missing.csv",
        allow_rule_fallback=True,
    )
    assert audit.ok is False
    assert audit.expected.expected_interval_source == "RULE_FALLBACK"
    assert "EXPECTED_INTERVAL_STATUS = REVIEW_REQUIRED" in audit.notes[0]


def test_table_stop_example_forbids_mainline():
    *_, result = _run("table_gate_stop_case.json", "missing_table.xlsx")
    assert result.stop is True
    assert result.table_read_confirmed == "NO"
    assert result.mainline_output_status == "FORBIDDEN"
    assert result.final_direction is None
