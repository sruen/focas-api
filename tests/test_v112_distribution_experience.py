from __future__ import annotations

from copy import deepcopy

import pytest

from focas_experience.report import build_experience_report
from focas_postmatch.review import build_postmatch_sample
from shared.fingerprint import (
    build_decision_key,
    build_fingerprint,
    build_structure_key_coarse,
    build_structure_key_exact,
    validate_fingerprint,
)
from shared.prematch_schema import PrematchSnapshot
from shared.result_schema import ResultPayload
from shared.validators import SharedValidationError


def _snapshot(
    *,
    distribution_type: str = "强主顺分布",
    theoretical_interval: str = "主低赔 / 5区 / 中水",
    home_pressure: str = "强",
    draw_pressure: str = "中",
    away_pressure: str = "弱",
    first_eye_direction: str = "主胜",
    dispersion_available: dict[str, bool] | None = None,
) -> PrematchSnapshot:
    return PrematchSnapshot.from_dict(
        {
            "schema_version": "0.2",
            "match_id": "测试-主队-客队",
            "competition": "测试联赛",
            "home_team": "主队",
            "away_team": "客队",
            "match_time": "2026-06-02 20:00",
            "neutral_ground": False,
            "source_type": "test",
            "source_files": [],
            "basic_face_complete": True,
            "basic_face_gaps": [],
            "home_strength_grade": "中上",
            "away_strength_grade": "中游",
            "strength_diff": "主队高一档",
            "dynamic_revision": None,
            "theoretical_system": "STRENGTH_INTERVAL_BRIDGE",
            "theoretical_interval": theoretical_interval,
            "theoretical_interval_source": "test",
            "actual_opening_interval": {
                "William": {"home": "2区低水", "draw": "3区中水", "away": "5区高水"},
                "Ladbrokes": {"home": "2区低水", "draw": "3区中水", "away": "5区高水"},
            },
            "actual_latest_interval": {
                "William": {"home": "2区低水", "draw": "3区中水", "away": "5区高水"},
                "Ladbrokes": {"home": "2区低水", "draw": "3区中水", "away": "5区高水"},
            },
            "opening_deviation": "表内",
            "odds_move_deviation": "动作摘要，不进入粗匹配",
            "original_distribution": {
                "distribution_type": distribution_type,
                "home_pressure": home_pressure,
                "draw_pressure": draw_pressure,
                "away_pressure": away_pressure,
                "first_eye_direction": first_eye_direction,
                "dispersion_available": dispersion_available
                if dispersion_available is not None
                else {"主胜": True, "平局": True, "客胜": False},
            },
            "company_motive_chain": {
                "opening": {"readings": []},
                "movement": {
                    "moves": [
                        {"direction": "主胜", "action": "抬高", "delta": 0.12},
                        {"direction": "平局", "action": "拉低", "delta": -0.08},
                        {"direction": "客胜", "action": "稳定", "delta": 0.0},
                    ],
                    "motive_readings": [],
                    "odds_face_change": "主抬_平降_负稳",
                },
                "closing": {"company_relation": {}},
            },
            "unfavorable_directions": [],
            "unfavorable_score_patterns": [],
            "relative_mainline_selection": "胜",
            "final_direction": "胜",
            "score_range": ["1-0", "2-0", "2-1"],
            "margin_targets": [1, 2],
            "evidence_gaps": [],
            "companies": ["William", "Ladbrokes"],
            "opening": {"William": [2.1, 3.2, 3.6], "Ladbrokes": [2.08, 3.25, 3.65]},
            "latest_or_closing": {"William": [2.12, 3.18, 3.58], "Ladbrokes": [2.1, 3.2, 3.6]},
            "final": None,
            "odds_pattern_tags": ["动作标签不进入粗结构键"],
            "company_alignment": "同向确认",
            "pre_match_summary": "测试快照",
        }
    )


def _sample(snapshot: PrematchSnapshot, sample_id: str):
    sample = build_postmatch_sample(snapshot, ResultPayload.from_dict({"home_goals": 1, "away_goals": 0, "logic_hit": True}))
    sample.sample_id = sample_id
    sample.match_id = sample_id
    return sample


def test_distribution_fingerprint_excludes_main_confidence_side_from_dispersion() -> None:
    fingerprint = build_fingerprint(_snapshot())
    distribution = fingerprint["distribution_fingerprint"]
    assert distribution["confidence_bearing_side"] == "胜"
    assert distribution["natural_heat_side"] == "胜"
    assert distribution["dispersion_sides"] == ["平"]
    assert distribution["distribution_subtype"] == "主胜强拉力_平局分流"
    assert distribution["danger_side"] == "胜"
    assert fingerprint["structure_key_coarse"] == "强主顺分布|主胜强拉力_平局分流|胜|胜|平|胜"


def test_distribution_fingerprint_can_use_draw_and_loss_dispersion() -> None:
    distribution = build_fingerprint(_snapshot(away_pressure="中"))["distribution_fingerprint"]
    assert distribution["dispersion_sides"] == ["平", "负"]
    assert distribution["distribution_subtype"] == "主胜强拉力_平负分流"


def test_distribution_fingerprint_away_confidence_uses_draw_dispersion() -> None:
    distribution = build_fingerprint(
        _snapshot(
            home_pressure="弱",
            draw_pressure="中",
            away_pressure="强",
            first_eye_direction="客胜",
            dispersion_available={"主胜": False, "平局": True, "客胜": True},
        )
    )["distribution_fingerprint"]
    assert distribution["confidence_bearing_side"] == "负"
    assert distribution["dispersion_sides"] == ["平"]
    assert distribution["distribution_subtype"] == "客胜强拉力_平局分流"


def test_distribution_fingerprint_draw_confidence_uses_win_loss_dispersion() -> None:
    distribution = build_fingerprint(
        _snapshot(
            home_pressure="中",
            draw_pressure="强",
            away_pressure="中",
            first_eye_direction="平局",
        )
    )["distribution_fingerprint"]
    assert distribution["confidence_bearing_side"] == "平"
    assert distribution["dispersion_sides"] == ["胜", "负"]
    assert distribution["distribution_subtype"] == "平局强拉力_胜负分流"


def test_distribution_fingerprint_allows_explicit_weak_receiving_side() -> None:
    distribution = build_fingerprint(
        _snapshot(dispersion_available={"主胜": True, "平局": True, "客胜": True})
    )["distribution_fingerprint"]
    assert distribution["dispersion_sides"] == ["平", "负"]


def test_coarse_key_uses_distribution_only() -> None:
    snapshot = _snapshot()
    fingerprint = build_fingerprint(snapshot)
    coarse = fingerprint["structure_key_coarse"]
    assert fingerprint["theoretical_interval"] not in coarse
    assert fingerprint["odds_move_deviation"] not in coarse
    opposite = PrematchSnapshot.from_dict({**snapshot.to_dict(), "final_direction": "负"})
    assert build_fingerprint(opposite)["structure_key_coarse"] == coarse
    assert coarse == build_structure_key_coarse(fingerprint["distribution_fingerprint"])
    assert fingerprint["distribution_fingerprint"]["confidence_bearing_side"] not in fingerprint["distribution_fingerprint"]["dispersion_sides"]


def test_exact_key_contains_interval_and_opening_coordinate_summary() -> None:
    fingerprint = build_fingerprint(_snapshot())
    exact = fingerprint["structure_key_exact"]
    assert fingerprint["theoretical_interval"] in exact
    assert "William" in exact
    assert "2区低水" in exact


def test_decision_key_contains_direction() -> None:
    fingerprint = build_fingerprint(_snapshot())
    decision = build_decision_key(
        structure_key_exact=fingerprint["structure_key_exact"],
        final_direction="胜",
        candidate_mainline="胜",
    )
    assert '"final_direction":"胜"' in decision


def test_movement_key_drops_delta_decimals() -> None:
    snapshot = _snapshot()
    data = snapshot.to_dict()
    data["company_motive_chain"]["movement"]["odds_face_change"] = "右倾 + 平负合力（转换后双公司均值变化：主胜+0.023/平局-0.030）"
    fingerprint = build_fingerprint(PrematchSnapshot.from_dict(data))
    assert "+0.023" not in fingerprint["movement_key"]
    assert "-0.030" not in fingerprint["movement_key"]


def test_same_distribution_different_interval_is_not_exact(monkeypatch) -> None:
    current = _snapshot()
    historical = _sample(_snapshot(theoretical_interval="主低赔 / 4区 / 中水"), "different-interval")
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: [historical])
    report = build_experience_report(build_fingerprint(current))
    assert report["distribution_matches"] == ["different-interval"]
    assert report["exact_interval_matches"] == []


def test_same_distribution_and_interval_is_exact(monkeypatch) -> None:
    snapshot = _snapshot()
    historical = _sample(snapshot, "exact")
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: [historical])
    report = build_experience_report(build_fingerprint(snapshot))
    assert report["exact_interval_matches"] == ["exact"]


def test_same_interval_different_distribution_is_not_exact(monkeypatch) -> None:
    current = _snapshot()
    historical = _sample(_snapshot(distribution_type="弱主逆分布"), "different-distribution")
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: [historical])
    report = build_experience_report(build_fingerprint(current))
    assert report["exact_interval_matches"] == []


def test_same_movement_different_distribution_is_only_weak(monkeypatch) -> None:
    current = _snapshot()
    historical = _sample(_snapshot(distribution_type="弱主逆分布"), "same-movement-only")
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: [historical])
    report = build_experience_report(build_fingerprint(current))
    assert report["movement_matches"] == []
    assert report["weak_matches"] == ["same-movement-only"]


def test_a_level_requires_five_exact_interval_samples(monkeypatch) -> None:
    snapshot = _snapshot()
    samples = [_sample(snapshot, f"exact-{index}") for index in range(5)]
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: samples)
    report = build_experience_report(build_fingerprint(snapshot))
    assert report["experience_level"] == "A"
    assert report["exact_interval_sample_count"] == 5
    assert report["usable_for_mainline"] is True


def test_b_level_uses_distribution_only_and_is_not_usable(monkeypatch) -> None:
    snapshot = _snapshot()
    samples = [_sample(snapshot, f"distribution-{index}") for index in range(5)]
    for index, sample in enumerate(samples):
        sample.structure_key_exact = f"different-exact-{index}"
        sample.decision_key = f"different-decision-{index}"
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: samples)
    report = build_experience_report(build_fingerprint(snapshot))
    assert report["experience_level"] == "B"
    assert report["distribution_sample_count"] == 5
    assert report["exact_interval_sample_count"] == 0
    assert report["usable_for_mainline"] is False


def test_decision_match_is_not_a_primary_entry(monkeypatch) -> None:
    snapshot = _snapshot()
    fingerprint = build_fingerprint(snapshot)
    historical = _sample(_snapshot(distribution_type="弱主逆分布"), "decision-only")
    historical.decision_key = fingerprint["decision_key"]
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: [historical])
    report = build_experience_report(fingerprint)
    assert report["decision_matches"] == ["decision-only"]
    assert report["distribution_matches"] == []
    assert report["matched_by"] == "weak_fields"
    assert report["experience_level"] == "D"


def test_incomplete_distribution_fingerprint_stays_d(monkeypatch) -> None:
    snapshot = _snapshot()
    fingerprint = build_fingerprint(snapshot)
    fingerprint["distribution_fingerprint"]["original_distribution_type"] = "未确认"
    monkeypatch.setattr("focas_experience.report.all_samples", lambda: [_sample(snapshot, "historical")])
    report = build_experience_report(fingerprint)
    assert report["fingerprint_complete"] is False
    assert report["experience_level"] == "D"
    assert report["usable_for_mainline"] is False


@pytest.mark.parametrize(
    "field",
    ["result", "outcome", "final_score", "home_goals", "away_goals", "goal_margin", "direction_hit", "score_range_hit", "margin_hit"],
)
def test_fingerprint_rejects_postmatch_fields(field: str) -> None:
    with pytest.raises(SharedValidationError):
        validate_fingerprint({field: "不得进入赛前 fingerprint"})
