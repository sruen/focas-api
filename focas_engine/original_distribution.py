from __future__ import annotations

from .models import MatchContext, NaturalPull, OriginalDistribution, StrengthContext
from .strength import grade_to_score

DIRECTIONS = ("主胜", "平局", "客胜")
PRESSURE_ORDER = {"弱": 0, "中": 1, "强": 2}


def _pull_map(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {p.direction: p for p in pulls}


def _gap(strength: StrengthContext) -> int:
    home = grade_to_score(strength.home_grade)
    away = grade_to_score(strength.away_grade)
    if home is None or away is None:
        return 0
    return home - away


def _pressure_label(score: float) -> str:
    if score >= 2:
        return "强"
    if score >= 1:
        return "中"
    return "弱"


def _pressures(
    *,
    match: MatchContext,
    strength: StrengthContext,
    pulls: list[NaturalPull],
) -> dict[str, str]:
    pmap = _pull_map(pulls)
    gap = _gap(strength)
    scores = {
        direction: float(PRESSURE_ORDER.get((pmap.get(direction).strength if pmap.get(direction) else None) or "弱", 0))
        for direction in DIRECTIONS
    }
    if gap >= 2:
        scores["主胜"] += 0.75
        scores["客胜"] -= 0.50
    elif gap <= -1:
        scores["客胜"] += 0.75
        scores["主胜"] -= 0.25
    if match.neutral_venue or match.real_home_away is False:
        scores["主胜"] -= 0.25
        scores["平局"] += 0.35
    text = " ".join(str(x) for x in (match.stage, match.match_type) if x)
    if any(key in text for key in ("决赛", "半决赛", "淘汰", "单回合")):
        scores["平局"] += 0.35
    return {direction: _pressure_label(score) for direction, score in scores.items()}


def _first_eye_direction(pulls: list[NaturalPull], pressures: dict[str, str]) -> str | None:
    explicit = [p.direction for p in pulls if p.first_eye_direction]
    if explicit:
        return max(explicit, key=lambda direction: PRESSURE_ORDER[pressures[direction]])
    ranked = sorted(DIRECTIONS, key=lambda direction: PRESSURE_ORDER[pressures[direction]], reverse=True)
    return ranked[0] if ranked and PRESSURE_ORDER[pressures[ranked[0]]] > 0 else None


def _distribution_type(
    *,
    match: MatchContext,
    strength: StrengthContext,
    pressures: dict[str, str],
) -> str:
    strong = {direction for direction, pressure in pressures.items() if pressure == "强"}
    if strong == {"主胜", "平局", "客胜"}:
        return "三项分散"
    if strong == {"主胜", "平局"}:
        return "胜平原始合力"
    if strong == {"平局", "客胜"}:
        return "平负原始合力"
    if strong == {"主胜", "客胜"}:
        return "胜负原始双分"
    if strong == {"主胜"}:
        return "单向主胜拉力"
    if strong == {"客胜"}:
        return "单向客胜拉力"
    if strong == {"平局"}:
        return "平局天然拉力"

    gap = _gap(strength)
    if match.neutral_venue or pressures["平局"] == "中":
        return "缓冲分布"
    if gap >= 1 and PRESSURE_ORDER[pressures["主胜"]] >= PRESSURE_ORDER[pressures["客胜"]]:
        return "顺分布"
    if gap <= -1 and PRESSURE_ORDER[pressures["客胜"]] >= PRESSURE_ORDER[pressures["主胜"]]:
        return "顺分布"
    if (gap >= 1 and PRESSURE_ORDER[pressures["客胜"]] > PRESSURE_ORDER[pressures["主胜"]]) or (
        gap <= 0 and PRESSURE_ORDER[pressures["主胜"]] > PRESSURE_ORDER[pressures["客胜"]]
    ):
        return "逆分布"
    return "中庸分布"


def build_original_distribution(
    *,
    match: MatchContext,
    strength: StrengthContext,
    pulls: list[NaturalPull],
) -> OriginalDistribution:
    """Build the pre-odds market distribution.

    This stage intentionally accepts no odds argument. It describes where the
    market is naturally likely to look before bookmaker prices are interpreted.
    """
    pressures = _pressures(match=match, strength=strength, pulls=pulls)
    pmap = _pull_map(pulls)
    first_eye = _first_eye_direction(pulls, pressures)
    weak = [direction for direction in DIRECTIONS if pressures[direction] == "弱"]
    dispersion = {
        direction: bool(
            pressures[direction] in {"强", "中"}
            or (pmap.get(direction) and pmap[direction].easy_to_receive)
        )
        for direction in DIRECTIONS
    }
    confidence_sources = []
    for direction in DIRECTIONS:
        pull = pmap.get(direction)
        if pull:
            confidence_sources.append(
                f"{direction}：自然拉力={pull.strength or '未知'}；事实={pull.facts or '未确认'}；"
                f"市场心理={pull.market_psychology or '未确认'}"
            )
    gap = _gap(strength)
    reasoning = [
        "原始分布只由基本面、广义实力和三项自然拉力生成；本阶段未读取赔率。",
        f"广义实力档位差={gap}；主胜/平局/客胜原始压力="
        f"{pressures['主胜']}/{pressures['平局']}/{pressures['客胜']}。",
        "原始分布强弱只用于解释后续赔率动作，不直接确认或排除任何方向。",
    ]
    if first_eye:
        reasoning.append(f"市场第一眼方向={first_eye}；后续需检查赔率是在承接、分散、保护还是打击该方向。")
    return OriginalDistribution(
        distribution_type=_distribution_type(match=match, strength=strength, pressures=pressures),
        home_pressure=pressures["主胜"],
        draw_pressure=pressures["平局"],
        away_pressure=pressures["客胜"],
        first_eye_direction=first_eye,
        confidence_sources=confidence_sources,
        weak_confidence_directions=weak,
        dispersion_available=dispersion,
        reasoning=reasoning,
    )


def pressure_by_direction(distribution: OriginalDistribution | None) -> dict[str, str]:
    if distribution is None:
        return {}
    return {
        "主胜": distribution.home_pressure,
        "平局": distribution.draw_pressure,
        "客胜": distribution.away_pressure,
    }
