from focas_engine.models import (
    CompanyRelationResult,
    DirectionJudgement,
    MatchContext,
    MotiveReading,
    NaturalPull,
    OpeningMotiveReading,
    OriginalBookMode,
    StrengthContext,
)
from focas_engine.relative_selection import select_relative_mainline


def test_relative_selection_after_one_adverse_keeps_categories_separate():
    judgements = [
        DirectionJudgement("主胜", "不利", ["测试不利"]),
        DirectionJudgement("平局", "中性", []),
        DirectionJudgement("客胜", "中性", []),
    ]
    strength = StrengthContext(home_grade="中游", away_grade="中上", static_gap="客队高一档", dynamic_adjustment="", final_gap="客队高一档", original_distribution="客向顺分布")
    pulls = [
        NaturalPull("主胜", "弱", "", "", "", False, False),
        NaturalPull("平局", "中", "", "", "", True, False),
        NaturalPull("客胜", "强", "", "", "", True, True),
    ]
    mode = OriginalBookMode(mode="平负合力 / 客胜信心区间", reason="客队拉力更强", key_odds_to_watch="客赔和平赔", easiest_misread="不能把未选中写成不利")
    match = MatchContext("A", "B", neutral_venue=False, single_leg=False)

    result = select_relative_mainline(
        judgements=judgements,
        strength=strength,
        pulls=pulls,
        book_mode=mode,
        table_results=[],
        motive_readings=[],
        match=match,
    )

    assert result.selected_direction == "客胜"
    assert result.adverse_exclusions == ["主胜"]
    assert "平局" in result.relative_non_selected
    by_dir = {s.direction: s for s in result.scores}
    assert by_dir["主胜"].excluded_by_adverse is True
    assert by_dir["平局"].excluded_by_adverse is False
    assert by_dir["客胜"].selected is True


def test_relative_selection_can_choose_from_no_adverse_but_marks_relative():
    judgements = [
        DirectionJudgement("主胜", "中性", []),
        DirectionJudgement("平局", "中性", []),
        DirectionJudgement("客胜", "中性", []),
    ]
    strength = StrengthContext(home_grade="中上", away_grade="中游", static_gap="主队高一档", dynamic_adjustment="", final_gap="主队高一档", original_distribution="顺分布")
    pulls = [
        NaturalPull("主胜", "强", "", "", "", True, True),
        NaturalPull("平局", "中", "", "", "", True, False),
        NaturalPull("客胜", "弱", "", "", "", False, False),
    ]
    mode = OriginalBookMode(mode="顺分布 / 强弱盘 / 胜赔手法", reason="主队高档", key_odds_to_watch="主赔", easiest_misread="抬高不等于不利")
    match = MatchContext("A", "B", neutral_venue=False, single_leg=False)

    result = select_relative_mainline(
        judgements=judgements,
        strength=strength,
        pulls=pulls,
        book_mode=mode,
        table_results=[],
        motive_readings=[],
        match=match,
    )

    assert result.selected_direction == "主胜"
    assert result.adverse_exclusions == []
    assert set(result.relative_non_selected) == {"平局", "客胜"}


def test_no_adverse_confidence_is_capped_at_medium():
    judgements = [
        DirectionJudgement("主胜", "中性", []),
        DirectionJudgement("平局", "中性", []),
        DirectionJudgement("客胜", "中性", []),
    ]
    strength = StrengthContext(home_grade="人强", away_grade="下游", static_gap="主队高多档", dynamic_adjustment="", final_gap="主队高多档", original_distribution="顺分布")
    pulls = [
        NaturalPull("主胜", "强", "", "", "", True, True),
        NaturalPull("平局", "弱", "", "", "", False, False),
        NaturalPull("客胜", "弱", "", "", "", False, False),
    ]
    mode = OriginalBookMode(mode="顺分布 / 强弱盘 / 胜赔手法", reason="主队明显高档", key_odds_to_watch="主赔", easiest_misread="无明确不利时不能高置信")
    match = MatchContext("A", "B", neutral_venue=False, single_leg=False)

    result = select_relative_mainline(
        judgements=judgements,
        strength=strength,
        pulls=pulls,
        book_mode=mode,
        table_results=[],
        motive_readings=[],
        match=match,
    )

    assert result.selected_direction == "主胜"
    assert result.adverse_exclusions == []
    assert result.confidence == "中"


def _opening_lure(company: str) -> OpeningMotiveReading:
    return OpeningMotiveReading(
        company=company,
        direction="主胜",
        opening_interval_id=7,
        expected_interval_id=5,
        interval_delta=2,
        natural_pull="强",
        original_pressure="强",
        first_eye_direction="主胜",
        uses_fundamental_pull=True,
        motive_type="利用基本面 / 主客场第一眼拉力压低初赔，利诱或过热风险候选",
        selection_constraint="REQUIRE_REVERSAL_CONFIRMATION",
    )


def _home_pull_selection_kwargs():
    return {
        "judgements": [
            DirectionJudgement("主胜", "未确认", []),
            DirectionJudgement("平局", "未确认", []),
            DirectionJudgement("客胜", "未确认", []),
        ],
        "strength": StrengthContext(
            home_grade="人强",
            away_grade="中游",
            static_gap="主队高多档",
            dynamic_adjustment="",
            final_gap="主队高多档",
            original_distribution="顺分布",
        ),
        "pulls": [
            NaturalPull("主胜", "强", "", "", "", True, True),
            NaturalPull("平局", "中", "", "", "", True, False),
            NaturalPull("客胜", "弱", "", "", "", False, False),
        ],
        "book_mode": OriginalBookMode(
            mode="顺分布 / 强弱盘 / 胜赔手法",
            reason="主队广义实力和主场拉力更强",
            key_odds_to_watch="主赔",
            easiest_misread="不能把基本面拉力直接等同结构方向",
        ),
        "table_results": [],
        "motive_readings": [],
        "match": MatchContext("A", "B", neutral_venue=False, single_leg=False),
        "opening_motive_readings": [_opening_lure("William"), _opening_lure("Ladbrokes")],
    }


def test_double_company_opening_lure_without_reversal_cannot_select_home():
    result = select_relative_mainline(**_home_pull_selection_kwargs())
    assert result.selected_direction != "主胜"
    home = next(item for item in result.scores if item.direction == "主胜")
    assert any("禁止仅凭基本面高分重新选回" in reason for reason in home.reasons)
    assert any("初赔一致性约束" in note for note in result.notes)


def test_double_company_opening_lure_can_return_after_reversal_confirmation():
    kwargs = _home_pull_selection_kwargs()
    kwargs["company_semantics"] = CompanyRelationResult(
        relation_type="同向确认",
        confirmed_directions=["主胜"],
        mainline_confirmed_directions=["主胜"],
    )
    result = select_relative_mainline(**kwargs)
    assert result.selected_direction == "主胜"
    home = next(item for item in result.scores if item.direction == "主胜")
    assert any("允许重新参与相对选择" in reason for reason in home.reasons)


def test_avg_motive_does_not_change_relative_selection_score():
    kwargs = _home_pull_selection_kwargs()
    kwargs["opening_motive_readings"] = []
    baseline = select_relative_mainline(**kwargs)
    kwargs["motive_readings"] = [
        MotiveReading("Avg", "主胜", "抬高", "强", "足", "中", "打击信心", "市场背景", True)
    ]
    with_avg = select_relative_mainline(**kwargs)
    baseline_scores = {item.direction: item.score for item in baseline.scores}
    with_avg_scores = {item.direction: item.score for item in with_avg.scores}
    assert with_avg_scores == baseline_scores
