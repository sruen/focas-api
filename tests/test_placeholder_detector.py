from focas_engine.checks import basic_context_gate
from focas_engine.models import H2HContext, MatchContext, TeamContext


def _valid_team(name: str) -> TeamContext:
    return TeamContext(
        name=name,
        rank="第1",
        points="80分",
        recent_matches=["2-0 A", "1-0 B", "2-1 C", "0-0 D", "3-1 E"],
        venue_adaptation="主场稳定，近5个主场4胜1平",
        attack_state="近5场进10球，进攻效率高",
        defense_state="近5场丢2球，防守稳定",
        injuries="主力齐整，仅替补伤缺",
        schedule_fatigue="一周一赛，体能正常",
        motivation="争冠关键战，战意明确",
        popularity_story="传统强队，人气高",
        major_recent_matches="近期击败直接竞争对手",
    )


def _valid_h2h() -> H2HContext:
    return H2HContext(
        overall="近10次5胜3平2负",
        recent_years="近3年主队略占优",
        same_competition="同赛事近4次2胜1平1负",
        venue_specific="主场近5次3胜1平1负",
        latest_key_match="最近一次2-1取胜",
        market_psychology="往绩增强主队市场信心",
    )


def test_placeholder_text_fails_basic_gate():
    home = _valid_team("主队")
    away = _valid_team("客队")
    home.attack_state = "进攻状态说明"
    match = MatchContext(
        home_team="主队",
        away_team="客队",
        competition="测试联赛",
        kickoff_time="2026-05-30 20:00",
        stage="第1轮",
        neutral_venue=False,
        single_leg=True,
        match_type="联赛",
        extra_time_or_penalties="无",
        real_home_away=True,
        attention_level="中",
        league_for_table="英超",
        home=home,
        away=away,
        h2h=_valid_h2h(),
    )
    gate = basic_context_gate(match)
    assert not gate.ok
    assert any("主队进攻状态" in item for item in gate.missing)


def test_valid_basic_context_passes_gate():
    match = MatchContext(
        home_team="主队",
        away_team="客队",
        competition="测试联赛",
        kickoff_time="2026-05-30 20:00",
        stage="第1轮",
        neutral_venue=False,
        single_leg=True,
        match_type="联赛",
        extra_time_or_penalties="无",
        real_home_away=True,
        attention_level="中",
        league_for_table="英超",
        home=_valid_team("主队"),
        away=_valid_team("客队"),
        h2h=_valid_h2h(),
    )
    assert basic_context_gate(match).ok


def test_placeholder_home_away_names_fail_basic_gate():
    match = MatchContext(
        home_team="主队名称",
        away_team="客队名称",
        competition="测试联赛",
        kickoff_time="2026-05-30 20:00",
        stage="第1轮",
        neutral_venue=False,
        single_leg=True,
        match_type="联赛",
        extra_time_or_penalties="无",
        real_home_away=True,
        attention_level="中",
        league_for_table="英超",
        home=_valid_team("主队名称"),
        away=_valid_team("客队名称"),
        h2h=_valid_h2h(),
    )
    gate = basic_context_gate(match)
    assert not gate.ok
    assert "主队名称" in gate.missing
    assert "客队名称" in gate.missing
    assert "主队队伍名称" in gate.missing
    assert "客队队伍名称" in gate.missing


def test_option_template_stage_fails_basic_gate():
    match = MatchContext(
        home_team="上海队",
        away_team="北京队",
        competition="测试联赛",
        kickoff_time="2026-05-30 20:00",
        stage="决赛/半决赛/联赛第X轮/小组赛第X轮",
        neutral_venue=False,
        single_leg=True,
        match_type="联赛",
        extra_time_or_penalties="无",
        real_home_away=True,
        attention_level="中",
        league_for_table="英超",
        home=_valid_team("上海队"),
        away=_valid_team("北京队"),
        h2h=_valid_h2h(),
    )
    gate = basic_context_gate(match)
    assert not gate.ok
    assert "比赛阶段" in gate.missing
