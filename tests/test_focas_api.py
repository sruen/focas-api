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
    audit = payload["opening_skeleton_audits"][0]
    assert audit["raw_opening_home"] is not None
    assert audit["expected_home_min"] is not None
    assert audit["expected_home_max"] is not None
