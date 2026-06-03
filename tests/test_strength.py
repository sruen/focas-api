from focas_engine.models import MatchContext, TeamContext
from focas_engine.strength import (
    STRENGTH_SOURCE_AUTO_ESTIMATED,
    STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED,
    STRENGTH_SOURCE_USER_PROVIDED,
    estimate_strength_context,
    fill_strength_context,
)
from focas_engine.models import StrengthContext


def test_rank_parser_prefers_ordinal_rank_over_date_year():
    match = MatchContext(
        home_team="A",
        away_team="B",
        home=TeamContext(name="A", rank="FIFA官方2026-04-01更新排名：第88位。"),
        away=TeamContext(name="B", rank="FIFA官方2026-04-01更新排名：第82位。"),
    )
    estimate = estimate_strength_context(match)
    assert estimate.home.rank_value == 88
    assert estimate.away.rank_value == 82


def test_strength_estimator_fills_missing_context():
    match = MatchContext(
        home_team="A",
        away_team="B",
        neutral_venue=False,
        match_type="联赛",
        home=TeamContext(
            name="A", rank="第1", points="80", recent_matches=["W", "W", "D", "W", "L"],
            venue_adaptation="主场强", attack_state="进攻稳定", defense_state="防守稳",
            injuries="阵容完整", schedule_fatigue="体能充足", motivation="争冠战意强",
            popularity_story="传统强队，人气高", major_recent_matches="击败强敌",
        ),
        away=TeamContext(
            name="B", rank="第12", points="40", recent_matches=["L", "D", "L", "W", "D"],
            venue_adaptation="客场差", attack_state="进攻低迷", defense_state="防守不稳",
            injuries="主力缺阵", schedule_fatigue="赛程密集", motivation="战意一般",
            popularity_story="人气低", major_recent_matches="无",
        ),
    )
    filled, estimate = fill_strength_context(StrengthContext(), match)
    assert filled.home_grade is not None
    assert filled.away_grade is not None
    assert filled.final_gap is not None
    assert estimate.home.score > estimate.away.score
    assert estimate.source == STRENGTH_SOURCE_AUTO_ESTIMATED


def test_user_provided_strength_source_is_preserved():
    match = MatchContext(home_team="A", away_team="B", home=TeamContext(name="A"), away=TeamContext(name="B"))
    manual = StrengthContext(
        home_grade="中上", away_grade="中游", static_gap="主队高一档",
        dynamic_adjustment="人工校准后维持", final_gap="主队高一档",
    )
    _, estimate = fill_strength_context(manual, match)
    assert estimate.source == STRENGTH_SOURCE_USER_PROVIDED


def test_unstable_auto_strength_requires_manual_review():
    match = MatchContext(home_team="A", away_team="B", home=TeamContext(name="A"), away=TeamContext(name="B"))
    _, estimate = fill_strength_context(StrengthContext(), match)
    assert estimate.source == STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED
