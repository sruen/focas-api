from __future__ import annotations

import re
from collections import Counter

from .models import FundamentalTopicAudit, FundamentalTopicItem, MatchContext, TeamContext
from .solution_audit import DIRECTIONS


DIRECTION_HOME, DIRECTION_DRAW, DIRECTION_AWAY = DIRECTIONS


def _parse_rank(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None


def _result_code(item: str) -> str | None:
    raw = str(item).strip()
    upper = raw.upper()
    if upper.startswith("W") or "胜" in raw or "勝" in raw:
        return "W"
    if upper.startswith("D") or "平" in raw:
        return "D"
    if upper.startswith("L") or "负" in raw or "敗" in raw or "败" in raw:
        return "L"
    score = re.search(r"(\d+)\s*[-:：]\s*(\d+)", raw)
    if score:
        left = int(score.group(1))
        right = int(score.group(2))
        if left > right:
            return "W"
        if left == right:
            return "D"
        return "L"
    return None


def _record(items: list[str]) -> tuple[int, int, int, int]:
    counts = Counter(_result_code(item) for item in items)
    wins = counts.get("W", 0)
    draws = counts.get("D", 0)
    losses = counts.get("L", 0)
    parsed = wins + draws + losses
    return wins, draws, losses, parsed


def _ppg(record: tuple[int, int, int, int]) -> float | None:
    wins, draws, _, parsed = record
    if parsed == 0:
        return None
    return (wins * 3 + draws) / parsed


def _strength_from_gap(gap: float, *, strong: float = 0.9, medium: float = 0.45) -> tuple[str, float]:
    amount = abs(gap)
    if amount >= strong:
        return "强", 0.95
    if amount >= medium:
        return "中", 0.65
    return "弱", 0.35


def _text_score(text: str | None, *, positive: tuple[str, ...], negative: tuple[str, ...]) -> int:
    if not text:
        return 0
    raw = str(text).lower()
    score = 0
    for item in positive:
        if item.lower() in raw:
            score += 1
    for item in negative:
        if item.lower() in raw:
            score -= 1
    return score


def _topic(
    *,
    category: str,
    direction: str,
    strength: str,
    visibility: str,
    score: float,
    facts: list[str],
    reason: str,
    options: list[str],
) -> FundamentalTopicItem:
    return FundamentalTopicItem(
        category=category,
        direction=direction,
        strength=strength,
        visibility=visibility,
        score=round(score, 4),
        facts=[item for item in facts if item],
        reason=reason,
        institution_use_options=options,
    )


def _team_name(team: TeamContext | None, fallback: str) -> str:
    return team.name if team and team.name else fallback


def _build_form_topic(match: MatchContext) -> tuple[FundamentalTopicItem, str]:
    home_record = _record(match.home.recent_matches if match.home else [])
    away_record = _record(match.away.recent_matches if match.away else [])
    home_ppg = _ppg(home_record)
    away_ppg = _ppg(away_record)
    home_name = _team_name(match.home, match.home_team)
    away_name = _team_name(match.away, match.away_team)
    summary = (
        f"{home_name}近况{home_record[0]}胜{home_record[1]}平{home_record[2]}负；"
        f"{away_name}近况{away_record[0]}胜{away_record[1]}平{away_record[2]}负"
    )
    if home_ppg is None or away_ppg is None:
        return _topic(
            category="近况",
            direction=DIRECTION_DRAW,
            strength="弱",
            visibility="中",
            score=0.20,
            facts=[summary],
            reason="近况无法稳定解析胜平负，只能作为低权重题材。",
            options=["保守分流", "降低单边判断权重"],
        ), summary

    gap = home_ppg - away_ppg
    if abs(gap) < 0.25:
        direction = DIRECTION_DRAW
        strength, score = "中", 0.55
        reason = "双方近况接近，近况更容易形成平局或分散单边受注题材。"
    else:
        direction = DIRECTION_HOME if gap > 0 else DIRECTION_AWAY
        strength, score = _strength_from_gap(gap)
        reason = "近况差形成可见受注题材。"
    return _topic(
        category="近况",
        direction=direction,
        strength=strength,
        visibility="高",
        score=score,
        facts=[summary],
        reason=reason,
        options=["吸收", "分流", "阻挡", "降热"],
    ), summary


def _build_h2h_topic(match: MatchContext) -> tuple[FundamentalTopicItem, str]:
    h2h = match.h2h
    facts = []
    if h2h:
        facts = [
            h2h.overall or "",
            h2h.recent_years or "",
            h2h.same_competition or "",
            h2h.venue_specific or "",
            h2h.market_psychology or "",
        ]
    joined = "；".join(item for item in facts if item)
    home_score = _text_score(joined, positive=("主队", "主场", "主胜", "优势", "占优"), negative=("客队占优", "客胜", "劣势"))
    away_score = _text_score(joined, positive=("客队", "客场", "客胜", "客队占优"), negative=("主队占优", "主胜"))
    if home_score - away_score >= 2:
        direction, strength, score, reason = DIRECTION_HOME, "中", 0.55, "往绩文字指向主队心理优势。"
    elif away_score - home_score >= 2:
        direction, strength, score, reason = DIRECTION_AWAY, "中", 0.55, "往绩文字指向客队心理优势。"
    else:
        direction, strength, score, reason = DIRECTION_DRAW, "弱", 0.30, "往绩没有形成稳定单边优势，更多作为中性分流题材。"
    return _topic(
        category="往绩",
        direction=direction,
        strength=strength,
        visibility="中",
        score=score,
        facts=[joined or "往绩资料未形成明确单边题材"],
        reason=reason,
        options=["分流", "心理阻挡", "题材放大"],
    ), joined


def _build_venue_topic(match: MatchContext) -> FundamentalTopicItem:
    if match.neutral_venue:
        return _topic(
            category="主客场",
            direction=DIRECTION_DRAW,
            strength="中",
            visibility="高",
            score=0.55,
            facts=["中立场或非真实主场，主队完整主场加成需要降权。"],
            reason="中立场最容易削弱主胜第一眼，并增加平局/客队分流能力。",
            options=["分流", "阻挡主胜", "降低主场热度"],
        )
    home_text = match.home.venue_adaptation if match.home else ""
    away_text = match.away.venue_adaptation if match.away else ""
    home_score = _text_score(home_text, positive=("强", "好", "稳定", "优势", "适应"), negative=("差", "不适应", "弱"))
    away_score = _text_score(away_text, positive=("强", "好", "稳定", "优势", "适应"), negative=("差", "不适应", "弱"))
    if match.real_home_away and home_score >= away_score:
        direction, strength, score, reason = DIRECTION_HOME, "中", 0.60, "真实主场与主队场地适应形成主胜题材。"
    elif away_score > home_score:
        direction, strength, score, reason = DIRECTION_AWAY, "弱", 0.35, "客队场地适应文字更好，可形成客队分流题材。"
    else:
        direction, strength, score, reason = DIRECTION_DRAW, "弱", 0.30, "场地题材没有明显单边。"
    return _topic(
        category="主客场",
        direction=direction,
        strength=strength,
        visibility="高",
        score=score,
        facts=[f"主队场地：{home_text}", f"客队场地：{away_text}"],
        reason=reason,
        options=["吸收", "分流", "阻挡"],
    )


def _build_injury_topic(match: MatchContext) -> FundamentalTopicItem:
    negative = ("伤", "缺", "停", "out", "injury", "injured", "suspended", "退役", "缺阵")
    positive = ("完整", "复出", "无重大", "齐整", "available", "return")
    home_score = _text_score(match.home.injuries if match.home else "", positive=positive, negative=negative)
    away_score = _text_score(match.away.injuries if match.away else "", positive=positive, negative=negative)
    gap = home_score - away_score
    if gap <= -1:
        direction, strength, score, reason = DIRECTION_AWAY, "中", 0.55, "主队伤停更重，形成客队或主胜反证题材。"
    elif gap >= 1:
        direction, strength, score, reason = DIRECTION_HOME, "中", 0.55, "客队伤停更重，形成主胜题材。"
    else:
        direction, strength, score, reason = DIRECTION_DRAW, "弱", 0.25, "伤停未形成明显单边差异。"
    return _topic(
        category="伤停",
        direction=direction,
        strength=strength,
        visibility="高",
        score=score,
        facts=[f"主队伤停：{match.home.injuries if match.home else ''}", f"客队伤停：{match.away.injuries if match.away else ''}"],
        reason=reason,
        options=["吸收", "压制", "制造阻力", "分流"],
    )


def _build_motivation_topic(match: MatchContext) -> FundamentalTopicItem:
    positive = ("必须", "争", "强", "明确", "晋级", "保级", "争冠", "战意足", "世界杯", "欧战")
    negative = ("轮换", "试阵", "无欲无求", "放弃", "提前", "友谊", "练兵")
    home_score = _text_score(match.home.motivation if match.home else "", positive=positive, negative=negative)
    away_score = _text_score(match.away.motivation if match.away else "", positive=positive, negative=negative)
    home_score += _text_score(match.home.schedule_fatigue if match.home else "", positive=("休整", "宽松"), negative=("疲劳", "密集", "少休"))
    away_score += _text_score(match.away.schedule_fatigue if match.away else "", positive=("休整", "宽松"), negative=("疲劳", "密集", "少休"))
    if home_score - away_score >= 1:
        direction, strength, score, reason = DIRECTION_HOME, "中", 0.55, "主队战意/赛程文字更好。"
    elif away_score - home_score >= 1:
        direction, strength, score, reason = DIRECTION_AWAY, "中", 0.55, "客队战意/赛程文字更好。"
    else:
        direction, strength, score, reason = DIRECTION_DRAW, "中", 0.45, "战意差异不明显，轮换或练兵更容易形成平局分流。"
    return _topic(
        category="战意赛程",
        direction=direction,
        strength=strength,
        visibility="中",
        score=score,
        facts=[
            f"主队战意/赛程：{match.home.motivation if match.home else ''}；{match.home.schedule_fatigue if match.home else ''}",
            f"客队战意/赛程：{match.away.motivation if match.away else ''}；{match.away.schedule_fatigue if match.away else ''}",
        ],
        reason=reason,
        options=["吸收", "分流", "阻挡", "诱导"],
    )


def _build_ranking_topic(match: MatchContext) -> FundamentalTopicItem:
    home_rank = _parse_rank(match.home.rank if match.home else None)
    away_rank = _parse_rank(match.away.rank if match.away else None)
    facts = [
        f"主队排名/积分：{match.home.rank if match.home else ''} / {match.home.points if match.home else ''}",
        f"客队排名/积分：{match.away.rank if match.away else ''} / {match.away.points if match.away else ''}",
        f"主队名气：{match.home.popularity_story if match.home else ''}",
        f"客队名气：{match.away.popularity_story if match.away else ''}",
    ]
    if home_rank is not None and away_rank is not None:
        gap = away_rank - home_rank
        if gap >= 20:
            direction, strength, score, reason = DIRECTION_HOME, "强", 0.95, "主队排名/名气优势明显，是大众第一眼题材。"
        elif gap >= 8:
            direction, strength, score, reason = DIRECTION_HOME, "中", 0.65, "主队排名/名气优势存在。"
        elif gap <= -20:
            direction, strength, score, reason = DIRECTION_AWAY, "强", 0.95, "客队排名/名气优势明显。"
        elif gap <= -8:
            direction, strength, score, reason = DIRECTION_AWAY, "中", 0.65, "客队排名/名气优势存在。"
        else:
            direction, strength, score, reason = DIRECTION_DRAW, "中", 0.45, "排名差距有限，容易形成均势或平局题材。"
    else:
        direction, strength, score, reason = DIRECTION_DRAW, "弱", 0.25, "排名无法稳定解析。"
    return _topic(
        category="排名名气",
        direction=direction,
        strength=strength,
        visibility="高",
        score=score,
        facts=facts,
        reason=reason,
        options=["吸收", "增信", "诱导", "分流"],
    )


def build_fundamental_topic_audit(match: MatchContext) -> FundamentalTopicAudit:
    form_topic, form_summary = _build_form_topic(match)
    h2h_topic, h2h_summary = _build_h2h_topic(match)
    audit = FundamentalTopicAudit(
        topics=[
            form_topic,
            h2h_topic,
            _build_venue_topic(match),
            _build_injury_topic(match),
            _build_motivation_topic(match),
            _build_ranking_topic(match),
        ],
        form_summary=form_summary,
        h2h_summary=h2h_summary,
        notes=[
            "基本面题材审计只判断市场可见题材，不等于赛果概率。",
            "近况、往绩、主客场、伤停、战意、排名名气必须先结构化，再进入三项拉力和最优解。",
        ],
    )
    return audit
