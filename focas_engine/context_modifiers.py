from __future__ import annotations

import re

from .event_context import is_knockout_like_context
from .models import EventContextModifiers, MatchContext


def _has_positive_rule(text: str, keyword: str) -> bool:
    if keyword not in text:
        return False
    return re.search(rf"(?:无|没有|不设|不含|无需)[^，。；]{{0,8}}{keyword}", text) is None


def build_event_context_modifiers(match: MatchContext) -> EventContextModifiers:
    text = " ".join(str(value) for value in (
        match.competition,
        match.stage,
        match.match_type,
        match.extra_time_or_penalties,
    ) if value)
    tags: list[str] = []
    for label, keywords in (
        ("联赛", ("联赛",)),
        ("杯赛", ("杯",)),
        ("小组赛", ("小组",)),
        ("淘汰赛", ("淘汰",)),
        ("决赛", ("决赛",)),
        ("半决赛", ("半决赛",)),
        ("国家队赛事", ("国家队", "国际", "世界杯", "欧洲杯", "美洲杯")),
        ("赛会制", ("赛会制", "集中赛会")),
    ):
        if any(keyword in text for keyword in keywords):
            tags.append(label)
    tags.append("单回合" if match.single_leg else "双回合或常规赛程")
    if match.neutral_venue:
        tags.append("中立场")
    if "加时" in text:
        tags.append("有加时" if _has_positive_rule(text, "加时") else "无加时")
    if "点球" in text:
        tags.append("有点球" if _has_positive_rule(text, "点球") else "无点球")

    home_motivation = getattr(match.home, "motivation", None) or "未提供"
    away_motivation = getattr(match.away, "motivation", None) or "未提供"
    home_schedule = getattr(match.home, "schedule_fatigue", None) or "未提供"
    away_schedule = getattr(match.away, "schedule_fatigue", None) or "未提供"
    neutral = bool(match.neutral_venue)
    real_home = match.real_home_away is True
    return EventContextModifiers(
        league_context_modifier=f"赛事语境={match.competition or '未提供'}；仅用于做盘语义修正",
        event_type_modifier=f"赛事类型修正={'、'.join(tags)}",
        neutral_field_modifier="中立场削弱真实主客优势" if neutral else "非中立场，保留场地语义",
        attention_level_modifier=f"关注度修正={match.attention_level or '未提供'}",
        home_advantage_modifier="真实主客属性存在" if real_home and not neutral else "主客优势需降权解释",
        draw_tendency_modifier="平局承接需提高权重" if neutral or is_knockout_like_context(match) else "平局承接按常规语境解释",
        motivation_modifier=f"战意修正：主队={home_motivation}；客队={away_motivation}",
        schedule_modifier=f"赛程修正：主队={home_schedule}；客队={away_schedule}",
        detected_event_tags=tags,
    )
