from __future__ import annotations

from collections import defaultdict

from .company_semantics import analyze_company_semantics
from .models import (
    CompanyRelationResult,
    MotiveReading,
    OddsFaceAndCompanyMotiveAnalysis,
    OddsMove,
    P1CoreResult,
)
from .odds_system import normalize_company

DIRECTIONS = ("主胜", "平局", "客胜")


def describe_odds_face(moves: list[OddsMove]) -> str:
    """Describe the three-way face from William/Ladbrokes published odds moves."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for move in moves:
        if normalize_company(move.company) not in {"William", "Ladbrokes"}:
            continue
        grouped[move.direction].append(move.delta)
    averages = {
        direction: (sum(grouped[direction]) / len(grouped[direction]) if grouped[direction] else 0.0)
        for direction in DIRECTIONS
    }
    home, draw, away = (averages[direction] for direction in DIRECTIONS)
    tags: list[str] = []
    if home < -0.005 and away > 0.005:
        tags.append("左倾")
    if away < -0.005 and home > 0.005:
        tags.append("右倾")
    if all(delta < -0.005 for delta in averages.values()):
        tags.append("收缩")
    if all(delta > 0.005 for delta in averages.values()):
        tags.append("扩张")
    if home < -0.005 and draw < -0.005:
        tags.append("胜平合力")
    if draw < -0.005 and away < -0.005:
        tags.append("平负合力")
    if home < -0.005 and away < -0.005 and draw >= -0.005:
        tags.append("胜负双分")
    if not tags:
        tags.append("中庸分布")
    delta_text = f"主胜{home:+.3f}/平局{draw:+.3f}/客胜{away:+.3f}"
    return f"{' + '.join(tags)}（机构原始赔率双公司均值变化：{delta_text}）"


def odds_face_and_company_motive_analysis(
    *,
    moves: list[OddsMove],
    motive_readings: list[MotiveReading],
    p1_core: P1CoreResult | None,
    odds_coordinates=None,
    opening_readings=None,
) -> OddsFaceAndCompanyMotiveAnalysis:
    """Stage 9: disassemble odds face, company roles and action motives."""
    relation: CompanyRelationResult = analyze_company_semantics(
        moves=moves,
        motive_readings=motive_readings,
        p1_core=p1_core,
        odds_coordinates=odds_coordinates,
    )
    william = next((reading for reading in relation.readings if reading.company == "威廉"), None)
    ladbrokes = next((reading for reading in relation.readings if reading.company == "立博"), None)
    misread_risks = sorted({
        reading.misread_risk
        for reading in motive_readings
        if reading.misread_risk
    })
    return OddsFaceAndCompanyMotiveAnalysis(
        odds_face_shape=describe_odds_face(moves),
        william_motive=william,
        ladbrokes_motive=ladbrokes,
        company_relation=relation,
        action_motive_chain=motive_readings,
        misread_risks=misread_risks,
        notes=[
            "先解释初赔目的，再解释即时变赔；初赔若利用基本面或主客场拉力形成利诱候选，后续必须出现反转确认才能重新取得结构方向资格。",
            "Stage 9 只拆盘：动作、赔面和公司目的必须一起解释，不直接输出最终方向。",
            "抬高 / 拉低只是赔率动作，不预设给信心、保护、分流或不利含义。",
            "Avg 只保留为市场背景，不进入 William / Ladbrokes 双公司确认关系。",
        ],
        opening_motive_chain=list(opening_readings or []),
    )
