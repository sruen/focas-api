from focas_engine.models import MatchContext, NaturalPull, OriginalBookMode, StrengthContext
from focas_engine.p1_core import build_p1_core


def test_p1_core_blocks_mechanical_home_odds_raise_misread():
    match = MatchContext(
        home_team="A",
        away_team="B",
        neutral_venue=False,
        real_home_away=True,
        match_type="联赛",
    )
    strength = StrengthContext(home_grade="普强", away_grade="中游", original_distribution="顺分布备选")
    pulls = [
        NaturalPull("主胜", "强", easy_to_receive=True, first_eye_direction=True),
        NaturalPull("平局", "强", easy_to_receive=True),
        NaturalPull("客胜", "弱", easy_to_receive=False),
    ]
    mode = OriginalBookMode(mode="顺分布 / 强弱盘")

    p1 = build_p1_core(match=match, strength=strength, pulls=pulls, book_mode=mode)
    home = {p.direction: p for p in p1.profiles}["主胜"]

    assert home.confidence_carrying in {"足", "中高"}
    assert home.can_bear_odds_raise is True
    assert any("主赔升" in b.pattern for b in p1.misread_blocks)
    assert p1.first_eye_direction == "主胜"


def test_p1_core_marks_weak_away_as_low_confidence():
    match = MatchContext(home_team="A", away_team="B", neutral_venue=False, match_type="联赛")
    strength = StrengthContext(home_grade="普强", away_grade="中下")
    pulls = [
        NaturalPull("主胜", "强", easy_to_receive=True, first_eye_direction=True),
        NaturalPull("平局", "中", easy_to_receive=True),
        NaturalPull("客胜", "弱", easy_to_receive=False),
    ]
    p1 = build_p1_core(match=match, strength=strength, pulls=pulls, book_mode=OriginalBookMode(mode="强弱盘"))
    away = {p.direction: p for p in p1.profiles}["客胜"]
    assert away.confidence_carrying == "弱"
    assert away.can_bear_odds_raise is False
    assert "拉低营造" in away.low_odds_decrease_meaning
