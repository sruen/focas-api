from focas_engine.models import MatchContext, NaturalPull, OriginalBookMode, StrengthContext
from focas_engine.original_modes import estimate_original_mode, fill_original_book_mode


def test_original_mode_estimator_detects_final_neutral_strong_match():
    match = MatchContext(
        home_team="A",
        away_team="B",
        competition="杯赛",
        stage="决赛",
        match_type="杯赛决赛",
        neutral_venue=True,
        single_leg=True,
        attention_level="高",
    )
    strength = StrengthContext(
        home_grade="普强",
        away_grade="普强",
        static_gap="双方同档或近似同档",
        dynamic_adjustment="接近",
        final_gap="双方同档或近似同档",
        original_distribution="中庸分布 / 强强或杯赛压缩备选",
    )
    pulls = [
        NaturalPull("主胜", "强", "A", "A", "A", True, True),
        NaturalPull("平局", "强", "D", "D", "D", True, False),
        NaturalPull("客胜", "强", "B", "B", "B", True, False),
    ]
    est = estimate_original_mode(match=match, strength=strength, pulls=pulls)
    assert "决赛盘" in est.primary_mode or any(c.mode == "决赛盘" for c in est.options)
    assert any("中立场盘" == c.mode for c in est.options)
    assert any("强强对话" in c.mode for c in est.options)


def test_original_mode_filler_respects_user_fields():
    match = MatchContext(home_team="A", away_team="B")
    strength = StrengthContext(home_grade="中游", away_grade="中游")
    pulls = [
        NaturalPull("主胜", "中", "A", "A", "A", True, True),
        NaturalPull("平局", "中", "D", "D", "D", True, False),
        NaturalPull("客胜", "中", "B", "B", "B", True, False),
    ]
    existing = OriginalBookMode(mode="人工模式")
    filled, est = fill_original_book_mode(existing, match=match, strength=strength, pulls=pulls)
    assert filled.mode == "人工模式"
    assert filled.reason is not None
    assert est.primary_mode


def test_human_strong_vs_midstrong_is_not_strong_strong_mode():
    match = MatchContext(home_team="A", away_team="B", match_type="联赛")
    strength = StrengthContext(home_grade="人强", away_grade="中强")
    pulls = [
        NaturalPull("主胜", "强", "A", "A", "A", True, True),
        NaturalPull("平局", "中", "D", "D", "D", True, False),
        NaturalPull("客胜", "弱", "B", "B", "B", False, False),
    ]
    estimate = estimate_original_mode(match=match, strength=strength, pulls=pulls)
    assert not any(option.mode == "强强对话 / 中庸分布" for option in estimate.options)


def test_gap_ge_2_prioritizes_strong_weak_mode():
    match = MatchContext(home_team="A", away_team="B", match_type="联赛")
    strength = StrengthContext(home_grade="人强", away_grade="中强")
    pulls = [
        NaturalPull("主胜", "强", "A", "A", "A", True, True),
        NaturalPull("平局", "中", "D", "D", "D", True, False),
        NaturalPull("客胜", "弱", "B", "B", "B", False, False),
    ]
    estimate = estimate_original_mode(match=match, strength=strength, pulls=pulls)
    assert estimate.options[0].mode == "顺分布 / 强弱盘 / 胜赔手法"
