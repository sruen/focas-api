from __future__ import annotations

import json
from pathlib import Path

from focas_api.service import analyze_match_input

PROJECT_ROOT = Path(__file__).parents[1]


def _valid_input():
    return json.loads((PROJECT_ROOT / "examples" / "valid_complete_match_input.json").read_text(encoding="utf-8"))


def test_api_contract_preserves_raw_institution_odds():
    payload = analyze_match_input(_valid_input())
    assert payload["analysis_contract"]["odds_numerical_conversion_allowed"] is False
    assert payload["analysis_contract"]["odds_comparison_basis"] == "raw_institution_odds"
    assert payload["system_routes"]
    assert all(item["numerical_conversion_applied"] is False for item in payload["system_routes"])
    william_opening = next(
        item for item in payload["system_routes"]
        if item["company"] == "William" and item["snapshot_type"] == "initial"
    )
    assert william_opening["raw_odds"] == [2.1, 3.2, 3.6]
    assert william_opening["target_sheet_system"] == "94系"


def test_api_exposes_opening_skeleton_audit_before_motive_chain():
    payload = analyze_match_input(_valid_input())
    assert payload["opening_skeleton_audits"]
    assert payload["opening_motive_chain"]
    assert payload["fundamental_topic_audit"]
    assert len(payload["fundamental_topic_audit"]["topics"]) >= 6
    audit = payload["opening_skeleton_audits"][0]
    assert audit["raw_opening_home"] is not None
    assert audit["expected_home_min"] is not None
    assert audit["expected_home_max"] is not None


def test_api_exposes_gpt_execution_gate_before_final_fields():
    payload = analyze_match_input(_valid_input())
    keys = list(payload)
    assert "gpt_execution_gate" in payload
    assert "movement_contradiction_audit" in payload
    assert keys.index("gpt_execution_gate") < keys.index("final_structure_judgement")
    gate = payload["gpt_execution_gate"]
    assert gate["final_direction_policy"] == "READ_LAST_ONLY"
    assert gate["all_three_scenarios_required"] is True
    assert gate["all_three_scenarios_present"] is True
    assert gate["final_output_allowed"] is True
    assert set(gate["scenario_directions_present"]) >= {"主胜", "平局", "客胜"}


def test_api_rejects_recent_matches_without_wdl_prefix():
    bad = _valid_input()
    bad["home_context"]["recent_matches"][0] = "2026-05-31 Home 0-2 Away"
    try:
        analyze_match_input(bad)
    except ValueError as exc:
        assert "must start with 'W ', 'D ', or 'L '" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("recent_matches without W/D/L prefix should be rejected")


def test_api_exposes_formal_development_audits():
    payload = analyze_match_input(_valid_input())
    assert payload["strength_dynamic_audit"]
    assert payload["original_distribution_audit"]
    assert payload["pre_odds_predicted_odds_audit"]
    assert payload["three_direction_development_matrix"]
    assert len(payload["three_direction_development_matrix"]) == 3
    assert {item["target_direction"] for item in payload["three_direction_development_matrix"]} == {"主胜", "平局", "客胜"}


def test_exact_predicted_odds_forbidden_without_formula():
    payload = analyze_match_input(_valid_input())
    audit = payload["pre_odds_predicted_odds_audit"]
    assert audit["calculation_status"] == "MISSING_FORMULA"
    assert audit["gpt_may_generate_exact_odds"] is False
    assert payload["gpt_execution_gate"]["exact_predicted_odds_allowed"] is False
    for item in payload["three_direction_development_matrix"]:
        assert item["predicted_odds"]["calculation_status"] == "MISSING_FORMULA"
        assert item["predicted_odds"]["exact_odds"] is None


def test_strength_dynamic_audit_uses_allowed_grades_only():
    payload = analyze_match_input(_valid_input())
    audit = payload["strength_dynamic_audit"]
    allowed = set(audit["allowed_grades"])
    assert {"下游", "中下", "中游", "中上", "中强", "准强", "普强", "人强"}.issubset(allowed)
    assert audit["home_grade"] in allowed
    assert audit["away_grade"] in allowed


def test_original_distribution_audit_exposes_distribution_type():
    payload = analyze_match_input(_valid_input())
    audit = payload["original_distribution_audit"]
    assert audit["distribution_type"]
    assert audit["home_pressure"]
    assert audit["draw_pressure"]
    assert audit["away_pressure"]
    assert audit["scenario_constraints"]
