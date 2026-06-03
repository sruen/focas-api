from __future__ import annotations

from pathlib import Path

import pytest

from focas_engine.io import load_input
from focas_engine.models import CompanyOdds, NarrativeMaterial, OddsSnapshot
from focas_engine.narrative_audit import build_narrative_audit
from focas_engine.odds_coordinate import build_odds_coordinates
from focas_engine.odds_system import build_odds_system_conversions
from focas_engine.pipeline import FocasPipeline
from focas_engine.report import render_frontend_report
from focas_engine.table_lookup import load_interval_profile


def _structured_materials() -> list[NarrativeMaterial]:
    return [
        NarrativeMaterial(
            direction=direction,
            topic=f"{direction}题材",
            facts="已核验事实",
            source="manual_verified_source",
            published_at="2026-06-02T00:00:00+08:00",
            visibility="高",
            strength="中",
            strength_alignment="与真实实力一致",
        )
        for direction in ("主胜", "平局", "客胜")
    ]


def test_structured_three_direction_narrative_audit_is_complete():
    audit = build_narrative_audit(pulls=[], materials=_structured_materials())
    assert audit.complete is True
    assert audit.review_required is False
    assert {item.direction for item in audit.direction_audits} == {"主胜", "平局", "客胜"}


def test_legacy_natural_pull_requires_source_level_review(mini_table):
    match, strength, pulls, mode, odds = load_input(Path("examples") / "valid_complete_match_input.json")
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is False
    assert result.narrative_audit.review_required is True
    assert result.final_structure_judgement is not None
    assert result.decision_status in {
        "EXECUTE",
        "LEAN",
        "BETTER_SOLUTION_ONLY",
        "NO_OPTIMAL_SOLUTION",
        "NO_BET_STRUCTURE",
        "PASS",
    }


def test_away_low_coordinate_keeps_home_axis_separate_from_actual_low(mini_table):
    odds = [
        CompanyOdds(
            "William",
            OddsSnapshot(home=3.20, draw=3.10, away=2.20),
            OddsSnapshot(home=3.30, draw=3.00, away=2.10),
        )
    ]
    coordinates = build_odds_coordinates(
        xlsx_path=mini_table,
        conversions=build_odds_system_conversions(odds),
    )
    current = coordinates.company_sets[0].current_low_coordinate()
    assert current is not None
    assert current.direction == "客胜"
    assert current.table_axis == "home"
    assert current.table_axis_odds == pytest.approx(current.odds_home)
    assert current.actual_low_odds == pytest.approx(current.odds_away)
    assert current.odds_value == pytest.approx(current.odds_away)


def test_away_low_pipeline_requires_skeleton_review(mini_table):
    match, strength, pulls, mode, odds = load_input(Path("examples") / "valid_complete_match_input.json")
    for company in odds:
        company.initial = OddsSnapshot(home=3.20, draw=3.10, away=2.20)
        company.current = OddsSnapshot(home=3.30, draw=3.00, away=2.10)
    result = FocasPipeline(table_path=mini_table).run(
        match=match,
        strength=strength,
        pulls=pulls,
        narrative_materials=_structured_materials(),
        book_mode=mode,
        odds=odds,
    )
    assert result.stop is False
    assert result.skeleton_scope_status == "HOME_AXIS_ONLY_REVIEW_REQUIRED"
    assert result.expected_interval_status == "REVIEW_REQUIRED"
    assert result.final_direction in {"PASS", "NO_BET", "主胜", "平局", "客胜"}


def test_opening_audit_reads_theoretical_range_from_detected_company_system(mini_table):
    match, strength, pulls, mode, odds = load_input(Path("examples") / "valid_complete_match_input.json")
    result = FocasPipeline(table_path=mini_table).run(
        match=match,
        strength=strength,
        pulls=pulls,
        narrative_materials=_structured_materials(),
        book_mode=mode,
        odds=odds,
    )
    assert result.interval_audit is not None
    assert result.interval_audit.ok is True
    assert len(result.interval_audit.audits) == 2
    for audit in result.interval_audit.audits:
        assert audit.system is not None
        assert audit.skeleton_profile_status == "PROFILE_CONFIRMED"
        assert audit.expected_home_min is not None
        assert audit.expected_home_max is not None
        assert audit.raw_opening_home is not None
        assert audit.price_reasonableness in {
            "DEEPER_THAN_THEORETICAL_RANGE",
            "WITHIN_THEORETICAL_RANGE",
            "SHALLOWER_THAN_THEORETICAL_RANGE",
        }
    assert result.psychological_interval_audit is not None
    assert {item.direction for item in result.psychological_interval_audit.direction_intervals} == {"主胜", "平局", "客胜"}
    assert result.opening_board_audit is not None
    assert len(result.opening_board_audit.company_audits) == 2
    for company_audit in result.opening_board_audit.company_audits:
        assert {item.direction for item in company_audit.direction_audits} == {"主胜", "平局", "客胜"}
    assert result.market_pull_audit is not None
    assert len(result.market_pull_audit.directions) == 3
    assert sum(item.pull_percent for item in result.market_pull_audit.directions) == pytest.approx(100.0)
    assert result.bookmaker_topic_usage_audit is not None
    assert result.optimal_solution_audit is not None
    assert result.optimal_solution_audit.solution_status in {
        "OPTIMAL_SOLUTION_FOUND",
        "BETTER_SOLUTION_ONLY",
        "NO_OPTIMAL_SOLUTION",
        "NO_BET_STRUCTURE",
    }
    assert result.final_structure_judgement is not None
    assert result.final_structure_judgement.status in {
        "EXECUTE",
        "LEAN",
        "BETTER_SOLUTION_ONLY",
        "NO_OPTIMAL_SOLUTION",
        "NO_BET_STRUCTURE",
    }


def test_frontend_report_exposes_opening_skeleton_reasonableness_audit(mini_table):
    match, strength, pulls, mode, odds = load_input(Path("examples") / "valid_complete_match_input.json")
    result = FocasPipeline(table_path=mini_table).run(
        match=match,
        strength=strength,
        pulls=pulls,
        narrative_materials=_structured_materials(),
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
    assert "初赔合理性审计：理论骨架 vs 机构实际初赔" in text
    assert "初赔体系" in text
    assert "理论主赔范围" in text
    assert "机构原始初赔" in text
    assert "赔率数值不做二次转换" in text
    assert "未确认骨架时，不得解释机构动机" in text
    assert "三项原始心理区间赔率" in text
    assert "三项初赔落点对照" in text
    assert "三项市场拉力与题材" in text
    assert "三项最优解 / 更优解" in text
    assert "后续机构做盘方向" in text


def test_unavailable_theoretical_interval_profile_requires_review(mini_table):
    profile = load_interval_profile(mini_table, "94系", 10)
    assert profile.status == "PROFILE_REVIEW_REQUIRED"
    assert profile.main_price_min is None
    assert profile.main_price_max is None
