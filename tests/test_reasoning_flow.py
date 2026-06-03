from focas_engine.checks import odds_system_conversion_gate, original_distribution_gate
from focas_engine.integrated_structure import integrated_structure_judgement
from focas_engine.models import (
    CompanyOdds,
    H2HContext,
    MatchContext,
    NaturalPull,
    OddsFaceAndCompanyMotiveAnalysis,
    OddsMove,
    OddsSnapshot,
    OriginalBookMode,
    OriginalDistribution,
    StrengthContext,
    TeamContext,
)
from focas_engine.motives import judge_odds_action_motive, odds_moves, opening_motive_readings
from focas_engine.odds_system import (
    build_odds_system_conversions,
    detect_nearest_available_system,
)
from focas_engine.original_distribution import build_original_distribution
from focas_engine.report import render_frontend_report
from focas_engine.stage9 import odds_face_and_company_motive_analysis
from focas_engine.models import PipelineResult
from focas_engine.pipeline import FocasPipeline


def _pulls():
    return [
        NaturalPull("主胜", "强", "主队实力", "主队人气", "主", True, True),
        NaturalPull("平局", "中", "杯赛谨慎", "平局心理", "平", True, False),
        NaturalPull("客胜", "弱", "客队承载弱", "客队心理弱", "客", False, False),
    ]


def _distribution():
    return OriginalDistribution(
        distribution_type="胜平原始合力",
        home_pressure="强",
        draw_pressure="中",
        away_pressure="弱",
        first_eye_direction="主胜",
        confidence_sources=["主胜事实"],
        weak_confidence_directions=["客胜"],
        dispersion_available={"主胜": True, "平局": True, "客胜": False},
        reasoning=["未读取赔率"],
    )


def _strength():
    return StrengthContext(
        home_grade="普强",
        away_grade="中游",
        static_gap="主队高两档",
        dynamic_adjustment="主队状态稳定",
        final_gap="主队高两档",
        theoretical_psychological_interval="主胜明确承接心理区间",
        theoretical_home_odds_range="1.60-1.95",
        theoretical_draw_odds_reference="3.30-4.10",
        theoretical_away_odds_reference="4.20-6.20",
    )


def test_original_distribution_required_before_odds_analysis():
    gate = original_distribution_gate(None)
    assert gate.ok is False
    assert "原始分布整体" in gate.missing


def test_original_distribution_does_not_exclude_direction_directly():
    match = MatchContext("A", "B", neutral_venue=False, real_home_away=True, match_type="联赛")
    distribution = build_original_distribution(match=match, strength=_strength(), pulls=_pulls())
    assert distribution.weak_confidence_directions
    assert not hasattr(distribution, "adverse_excluded_directions")
    assert any("不直接确认或排除" in reason for reason in distribution.reasoning)


def test_detect_nearest_available_system():
    system, distance, status = detect_nearest_available_system(93.6)
    assert system == "94系"
    assert distance == 0.4
    assert status == "NEAREST_AVAILABLE_SYSTEM"


def test_avg_cannot_replace_william_ladbrokes():
    avg = [CompanyOdds("Avg", OddsSnapshot(2.0, 3.2, 3.8), OddsSnapshot(2.1, 3.1, 3.7))]
    gate = odds_system_conversion_gate(build_odds_system_conversions(avg))
    assert gate.ok is False
    assert any("William" in item for item in gate.missing)
    assert any("Ladbrokes" in item for item in gate.missing)


def test_odds_raise_has_no_preset_meaning():
    reading = judge_odds_action_motive(
        odds_action=OddsMove("William", "主胜", 2.0, 2.1, 0.1, "抬高"),
        original_distribution=None,
        natural_pull=None,
        strength_gap=None,
        expected_interval=None,
        table_position="未查表",
        odds_face="待判断",
        company_context="William",
    )
    assert reading.adverse_evidence is False
    assert "待判断" in reading.motive_type


def test_odds_drop_has_no_preset_meaning():
    reading = judge_odds_action_motive(
        odds_action=OddsMove("William", "平局", 3.2, 3.1, -0.1, "拉低"),
        original_distribution=None,
        natural_pull=None,
        strength_gap=None,
        expected_interval=None,
        table_position="未查表",
        odds_face="待判断",
        company_context="William",
    )
    assert reading.adverse_evidence is False
    assert "待判断" in reading.motive_type


def test_odds_action_requires_motive_judgement():
    moves = odds_moves([CompanyOdds("William", OddsSnapshot(2.0, 3.2, 3.8), OddsSnapshot(2.1, 3.1, 3.8))])
    assert {move.action for move in moves} >= {"抬高", "拉低"}
    assert all(not hasattr(move, "adverse_evidence") for move in moves)


def test_opening_motive_identifies_fundamental_lure_risk():
    audit = type("Audit", (), {
        "company": "William",
        "opening_low_direction": "主胜",
        "opening_interval_id": 7,
        "expected_interval_id": 5,
        "interval_delta": 2,
    })()
    interval_audit = type("IntervalAudit", (), {"audits": [audit]})()
    readings = opening_motive_readings(
        interval_audit=interval_audit,
        original_distribution=_distribution(),
        pulls=_pulls(),
        context_summary="真实主客属性存在",
    )
    assert len(readings) == 1
    assert readings[0].uses_fundamental_pull is True
    assert readings[0].selection_constraint == "REQUIRE_REVERSAL_CONFIRMATION"
    assert "利诱或过热风险候选" in readings[0].motive_type


def test_unconfirmed_cannot_exclude_direction():
    stage_9 = OddsFaceAndCompanyMotiveAnalysis("待判断", None, None, None, [], [], [])
    stage_9.company_relation = type("Relation", (), {
        "risk_repair_directions": [],
        "adverse_pressure_directions": [],
        "confirmed_directions": [],
    })()
    integrated = integrated_structure_judgement(
        strength=_strength(),
        pulls=_pulls(),
        original_distribution=_distribution(),
        book_mode=OriginalBookMode(mode="顺分布"),
        odds_coordinates=None,
        interval_audit=None,
        stage_9=stage_9,
    )
    assert integrated.adverse_excluded_directions == []
    assert "客胜" in integrated.unconfirmed_directions


def test_stage_9_disassembles_odds_and_motive():
    moves = [
        OddsMove("William", "主胜", 2.0, 2.1, 0.1, "抬高", "raw_institution_odds"),
        OddsMove("Ladbrokes", "平局", 3.2, 3.1, -0.1, "拉低", "raw_institution_odds"),
    ]
    motives = [
        judge_odds_action_motive(
            odds_action=move,
            original_distribution=_distribution(),
            natural_pull=next(p for p in _pulls() if p.direction == move.direction),
            strength_gap="主队高两档",
            expected_interval=None,
            table_position="表内",
            odds_face="组合待判断",
            company_context=move.company,
        )
        for move in moves
    ]
    result = odds_face_and_company_motive_analysis(moves=moves, motive_readings=motives, p1_core=None)
    assert result.odds_face_shape
    assert result.action_motive_chain == motives
    assert result.company_relation is not None


def test_stage_10_requires_integrated_reasoning():
    stage_9 = OddsFaceAndCompanyMotiveAnalysis("胜平合力", None, None, None, [], [], [])
    stage_9.company_relation = type("Relation", (), {
        "risk_repair_directions": [],
        "adverse_pressure_directions": [],
        "confirmed_directions": [],
    })()
    result = integrated_structure_judgement(
        strength=_strength(),
        pulls=_pulls(),
        original_distribution=_distribution(),
        book_mode=OriginalBookMode(mode="胜平原始合力"),
        odds_coordinates=None,
        interval_audit=None,
        stage_9=stage_9,
    )
    assert "广义实力" in result.home_integrated_judgement
    assert "原始压力" in result.draw_integrated_judgement
    assert result.summary_status


def test_report_contains_reasoning_flow_sections():
    result = PipelineResult(gates=[])
    result.original_distribution = _distribution()
    text = render_frontend_report(
        match=MatchContext("A", "B"),
        strength=_strength(),
        pulls=_pulls(),
        book_mode=OriginalBookMode(mode="顺分布"),
        odds=[],
        result=result,
    )
    assert "# FOCAS STOP_REPORT_ONLY" in text
    assert "## 当前禁止项" in text
    assert "## 1. 先说人话" not in text


def _team(name):
    return TeamContext(
        name=name,
        rank="第5",
        points="50分",
        recent_matches=["W 1-0", "D 1-1", "L 0-1", "W 2-0", "D 0-0"],
        venue_adaptation="适应",
        attack_state="稳定",
        defense_state="稳定",
        injuries="阵容完整",
        schedule_fatigue="正常",
        motivation="战意正常",
        popularity_story="有一定人气",
        major_recent_matches="近期表现正常",
    )


def test_pipeline_runs_complete_reasoning_flow(mini_table):
    match = MatchContext(
        home_team="A",
        away_team="B",
        competition="测试联赛",
        kickoff_time="2026-06-01 20:00",
        stage="联赛第1轮",
        neutral_venue=False,
        single_leg=False,
        match_type="联赛",
        extra_time_or_penalties="无",
        real_home_away=True,
        attention_level="中",
        league_for_table="英超",
        home=_team("A"),
        away=_team("B"),
        h2h=H2HContext(
            overall="总体均衡",
            recent_years="近年均衡",
            same_competition="同赛事均衡",
            venue_specific="主客均衡",
            latest_key_match="最近一次平局",
            market_psychology="往绩增加平局承接",
        ),
    )
    odds = [
        CompanyOdds("William", OddsSnapshot(2.10, 3.20, 3.60), OddsSnapshot(2.12, 3.18, 3.58)),
        CompanyOdds("Ladbrokes", OddsSnapshot(2.08, 3.25, 3.65), OddsSnapshot(2.10, 3.20, 3.60)),
        CompanyOdds("Avg", OddsSnapshot(2.09, 3.22, 3.62), OddsSnapshot(2.11, 3.19, 3.59)),
    ]
    result = FocasPipeline(table_path=mini_table).run(
        match=match,
        strength=StrengthContext(),
        pulls=_pulls(),
        book_mode=OriginalBookMode(),
        odds=odds,
    )
    assert result.stop is False
    assert result.original_distribution is not None
    assert len(result.odds_system_conversions) == 6
    assert result.stage_9_analysis is not None
    assert result.integrated_structure is not None
    assert result.relative_selection is not None
    assert result.final_direction
    report = render_frontend_report(
        match=match,
        strength=StrengthContext(),
        pulls=_pulls(),
        book_mode=OriginalBookMode(),
        odds=odds,
        result=result,
    )
    for hidden in ("Stage 9", "Stage 10", "Mainline_Output", "Basic_Context_Status"):
        assert hidden not in report
    assert "lookup_status" in report
    assert "初赔目的链" in report
    assert report.index("初赔目的链") < report.index("William 公司目的链")
