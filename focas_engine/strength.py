from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .models import MatchContext, StrengthContext, TeamContext


GRADE_ORDER = ["下游", "中下", "中游", "中上", "中强", "准强", "普强", "人强"]
GRADE_SCORE = {grade: idx * 0.5 for idx, grade in enumerate(GRADE_ORDER)}
ALLOWED_GRADES = set(GRADE_ORDER)
_MODERN_GRADE_ORDER = ["下游", "中下", "中游", "中上", "中强", "准强", "普强", "人强"]
GRADE_SCORE.update({grade: idx * 0.5 for idx, grade in enumerate(_MODERN_GRADE_ORDER)})
ALLOWED_GRADES.update(_MODERN_GRADE_ORDER)

STRENGTH_SOURCE_USER_PROVIDED = "USER_PROVIDED"
STRENGTH_SOURCE_AUTO_ESTIMATED = "AUTO_ESTIMATED"
STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass
class TeamStrengthEstimate:
    team: str
    side: str
    score: float
    grade: str
    rank_value: Optional[int] = None
    recent_points_per_game: Optional[float] = None
    components: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class StrengthEstimateResult:
    home: TeamStrengthEstimate
    away: TeamStrengthEstimate
    static_gap_steps: int
    dynamic_gap_steps: int
    final_gap_steps: int
    final_gap_label: str
    original_distribution: str
    theoretical_psychological_interval: str
    theoretical_home_odds_range: str
    theoretical_draw_odds_reference: str
    theoretical_away_odds_reference: str
    confidence: str
    warnings: list[str] = field(default_factory=list)
    static_gap_value: float = 0.0
    dynamic_gap_value: float = 0.0
    final_gap_value: float = 0.0
    source: str = STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED
    source_reason: str = ""


def grade_to_score(grade: str | None) -> Optional[float]:
    if not grade:
        return None
    return GRADE_SCORE.get(grade.strip())


def score_to_grade(score: float) -> str:
    """Map a 0-7 estimator score to the project grade ladder."""
    idx = int(round(max(0, min(7, score))))
    return GRADE_ORDER[idx]


def _parse_first_int(text: str | None) -> Optional[int]:
    if not text:
        return None
    raw = str(text)
    modern = re.search(r"第\s*(\d+)\s*(位|名)?", raw)
    if modern:
        return int(modern.group(1))
    ordinal = re.search(r"第\s*(\d+)\s*位", raw)
    if ordinal:
        return int(ordinal.group(1))
    m = re.search(r"\d+", raw)
    return int(m.group()) if m else None


def _recent_result_points(item: str) -> Optional[int]:
    s = item.strip().upper()
    if not s:
        return None
    if s.startswith("W") or "胜" in s:
        return 3
    if s.startswith("D") or "平" in s:
        return 1
    if s.startswith("L") or "负" in s or "败" in s:
        return 0
    return None


def _recent_ppg(recent_matches: list[str]) -> Optional[float]:
    pts = [_recent_result_points(x) for x in recent_matches]
    pts = [p for p in pts if p is not None]
    if not pts:
        return None
    return sum(pts) / len(pts)


def _keyword_delta(text: str | None, positive: tuple[str, ...], negative: tuple[str, ...], weight: float) -> tuple[float, list[str]]:
    if not text:
        return 0.0, []
    notes: list[str] = []
    raw = str(text)
    has_negative = any(k in raw for k in negative)
    has_positive = any(k in raw for k in positive)

    # Negative wording should override broad positive substrings such as “稳” inside “不稳”
    # or “完整” inside “不算完整”. This keeps the estimator conservative.
    if has_negative:
        notes.append(f"负向：{raw}")
        return -weight, notes
    if has_positive:
        notes.append(f"正向：{raw}")
        return weight, notes
    return 0.0, notes


def _rank_component(rank_value: Optional[int]) -> float:
    """
    Rank is only an auxiliary proxy. It deliberately does not dominate grade,
    because FOCAS treats ranking as a market-factor that can be错位 with broad strength.
    """
    if rank_value is None:
        return 3.0
    if rank_value <= 1:
        return 6.4
    if rank_value <= 3:
        return 5.7
    if rank_value <= 5:
        return 5.0
    if rank_value <= 8:
        return 4.1
    if rank_value <= 12:
        return 3.0
    if rank_value <= 16:
        return 2.0
    return 1.0


def _form_component(ppg: Optional[float]) -> float:
    if ppg is None:
        return 0.0
    # Convert recent PPG to a mild adjustment. Strong form should modify, not replace, base grade.
    if ppg >= 2.4:
        return 0.70
    if ppg >= 2.0:
        return 0.45
    if ppg >= 1.5:
        return 0.20
    if ppg >= 1.0:
        return -0.10
    if ppg >= 0.6:
        return -0.35
    return -0.65


def estimate_team_strength(team: TeamContext, *, side: str) -> TeamStrengthEstimate:
    rank_value = _parse_first_int(team.rank)
    ppg = _recent_ppg(team.recent_matches)

    components: dict[str, float] = {}
    notes: list[str] = []

    components["rank_base"] = _rank_component(rank_value)
    components["recent_form"] = _form_component(ppg)

    attack_delta, attack_notes = _keyword_delta(
        team.attack_state,
        positive=("强", "好", "稳定", "火力", "连续进球", "效率高", "爆发", "流畅"),
        negative=("弱", "差", "低迷", "哑火", "效率低", "乏力", "进攻问题"),
        weight=0.25,
    )
    components["attack"] = attack_delta
    notes.extend(attack_notes)

    defense_delta, defense_notes = _keyword_delta(
        team.defense_state,
        positive=("防守稳", "稳定", "好", "零封", "失球少", "防守强", "完整"),
        negative=("差", "漏洞", "失球多", "不稳", "崩", "伤缺"),
        weight=0.25,
    )
    components["defense"] = defense_delta
    notes.extend(defense_notes)

    injury_delta, injury_notes = _keyword_delta(
        team.injuries,
        positive=("齐整", "阵容完整", "完整", "复出", "主力回归", "无重大伤停"),
        negative=("严重伤停", "多人伤停", "伤停严重", "缺阵", "停赛", "核心缺", "主力缺", "不完整", "不算完整"),
        weight=0.35,
    )
    components["squad"] = injury_delta
    notes.extend(injury_notes)

    schedule_delta, schedule_notes = _keyword_delta(
        team.schedule_fatigue,
        positive=("休整", "体能充足", "赛程宽松", "以逸待劳"),
        negative=("疲劳", "密集", "连续客场", "少休", "消耗", "加时"),
        weight=0.25,
    )
    components["schedule"] = schedule_delta
    notes.extend(schedule_notes)

    motivation_delta, motivation_notes = _keyword_delta(
        team.motivation,
        positive=("强", "必须", "争冠", "争四", "保级", "晋级", "复仇", "战意足"),
        negative=("无欲无求", "轮换", "放弃", "战意弱", "提前出线", "已夺冠"),
        weight=0.30,
    )
    components["motivation"] = motivation_delta
    notes.extend(motivation_notes)

    popularity_delta, popularity_notes = _keyword_delta(
        team.popularity_story,
        positive=("豪门", "冠军", "名气", "人气", "卫冕", "传统强队"),
        negative=("升班马", "冷门", "人气低", "关注低"),
        weight=0.35,
    )
    components["popularity"] = popularity_delta
    notes.extend(popularity_notes)

    venue_delta, venue_notes = _keyword_delta(
        team.venue_adaptation,
        positive=("主场强", "适应", "优势", "中立适应好", "客场强"),
        negative=("客场虫", "不适应", "主场差", "中立不利", "客场差"),
        weight=0.25,
    )
    components["venue"] = venue_delta
    notes.extend(venue_notes)

    score = sum(components.values())
    grade = score_to_grade(score)

    if rank_value is None:
        notes.append("排名无法解析，rank_base 使用中性值。")
    if ppg is None:
        notes.append("近况无法解析胜平负，recent_form 不参与有效修正。")

    return TeamStrengthEstimate(
        team=team.name,
        side=side,
        score=round(score, 3),
        grade=grade,
        rank_value=rank_value,
        recent_points_per_game=round(ppg, 3) if ppg is not None else None,
        components={k: round(v, 3) for k, v in components.items()},
        notes=notes,
    )


def _gap_label(steps: int) -> str:
    if steps >= 3:
        return "主队明显高档"
    if steps == 2:
        return "主队高两档"
    if steps == 1:
        return "主队高一档"
    if steps == 0:
        return "双方同档或近似同档"
    if steps == -1:
        return "客队高一档"
    if steps == -2:
        return "客队高两档"
    return "客队明显高档"


def _round_to_half(value: float) -> float:
    return round(value * 2) / 2


def _gap_label_value(value: float) -> str:
    if value >= 2.5:
        return "主队明显高档"
    if value <= -2.5:
        return "客队明显高档"
    if abs(value) < 0.25:
        return "双方同档或近似同档"
    side = "主队" if value > 0 else "客队"
    amount = abs(value)
    if amount == 0.5:
        return f"{side}高0.5档"
    if amount == 1.0:
        return f"{side}高一档"
    if amount == 1.5:
        return f"{side}高1.5档"
    if amount == 2.0:
        return f"{side}高两档"
    return f"{side}高{amount:g}档"


def _distribution_from_gap(gap_value: float, match: MatchContext) -> str:
    # This is a conservative first-pass classification; original mode may override it.
    if match.neutral_venue or (match.match_type and any(k in match.match_type for k in ("决赛", "淘汰", "杯"))):
        if abs(gap_value) <= 0.5:
            return "中庸分布 / 强强或杯赛压缩备选"
        return "顺分布 / 强弱盘备选"
    if gap_value >= 1.0:
        return "顺分布备选"
    if gap_value <= -0.5:
        return "逆分布或客向顺分布备选"
    return "中庸分布备选"


def _theoretical_odds_references(final_gap_value: float) -> tuple[str, str, str, str]:
    """Return a conservative psychological interval, not a bookmaker quote."""
    if final_gap_value >= 2.5:
        return "主胜深承接心理区间", "1.35-1.65", "3.80-4.80", "5.50-8.50"
    if final_gap_value >= 1.5:
        return "主胜明确承接心理区间", "1.60-1.95", "3.30-4.10", "4.20-6.20"
    if final_gap_value >= 0.5:
        return "主胜浅承接心理区间", "1.90-2.35", "3.00-3.70", "3.00-4.40"
    if final_gap_value <= -1.5:
        return "客胜明确承接心理区间", "3.60-5.80", "3.10-4.00", "1.65-2.10"
    if final_gap_value <= -0.5:
        return "客胜浅承接心理区间", "2.45-3.40", "2.90-3.60", "2.10-2.85"
    return "均势 / 中庸心理区间", "2.25-2.95", "2.85-3.45", "2.45-3.30"


def estimate_strength_context(match: MatchContext) -> StrengthEstimateResult:
    if match.home is None or match.away is None:
        raise ValueError("基本面缺少主队或客队 TeamContext，不能估算广义实力。")

    home_est = estimate_team_strength(match.home, side="主队")
    away_est = estimate_team_strength(match.away, side="客队")

    static_gap = grade_to_score(home_est.grade) - grade_to_score(away_est.grade)  # type: ignore[operator]
    raw_score_gap = (home_est.score - away_est.score) / 2
    dynamic_gap_value = _round_to_half(raw_score_gap - static_gap)
    final_gap_value = _round_to_half(raw_score_gap)
    dynamic_gap = int(round(dynamic_gap_value * 2))
    final_gap = int(round(final_gap_value * 2))
    distribution = _distribution_from_gap(final_gap_value, match)
    psychological, home_range, draw_reference, away_reference = _theoretical_odds_references(final_gap_value)

    warnings: list[str] = [
        "strength.py 是辅助分档器，不替代人工广义实力校准；强队底蕴、联赛差异、欧战人气仍需人工确认。"
    ]
    if home_est.rank_value is None or away_est.rank_value is None:
        warnings.append("至少一队排名无法解析，分档置信度下降。")
    if home_est.recent_points_per_game is None or away_est.recent_points_per_game is None:
        warnings.append("至少一队近况无法解析，动态修正置信度下降。")

    confidence = "中"
    if len(warnings) > 1:
        confidence = "低"
    elif abs(raw_score_gap) >= 1.5:
        confidence = "中高"

    return StrengthEstimateResult(
        home=home_est,
        away=away_est,
        static_gap_steps=int(round(static_gap * 2)),
        dynamic_gap_steps=int(dynamic_gap),
        final_gap_steps=int(final_gap),
        final_gap_label=_gap_label_value(final_gap_value),
        original_distribution=distribution,
        theoretical_psychological_interval=psychological,
        theoretical_home_odds_range=home_range,
        theoretical_draw_odds_reference=draw_reference,
        theoretical_away_odds_reference=away_reference,
        confidence=confidence,
        warnings=warnings,
        static_gap_value=float(static_gap),
        dynamic_gap_value=float(dynamic_gap_value),
        final_gap_value=float(final_gap_value),
    )


def fill_strength_context(existing: StrengthContext, match: MatchContext) -> tuple[StrengthContext, StrengthEstimateResult | None]:
    """
    Fill missing StrengthContext fields from the estimator.
    User-provided fields always win. This makes v0.2 operational without hiding uncertainty.
    """
    estimate = estimate_strength_context(match)
    explicit_fields = (
        existing.home_grade,
        existing.away_grade,
        existing.static_gap,
        existing.dynamic_adjustment,
        existing.final_gap,
    )
    explicit_grades_valid = (
        existing.home_grade in ALLOWED_GRADES
        and existing.away_grade in ALLOWED_GRADES
    )
    if all(explicit_fields) and explicit_grades_valid:
        estimate.source = STRENGTH_SOURCE_USER_PROVIDED
        estimate.source_reason = "输入包明确提供了双方正式档位、静态档位差、动态修正和最终动态关系。"
    elif existing.home_grade and existing.home_grade not in ALLOWED_GRADES:
        estimate.source = STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED
        estimate.source_reason = f"主队广义实力档位不在正式枚举内：{existing.home_grade}。"
    elif existing.away_grade and existing.away_grade not in ALLOWED_GRADES:
        estimate.source = STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED
        estimate.source_reason = f"客队广义实力档位不在正式枚举内：{existing.away_grade}。"
    elif (
        estimate.home.rank_value is None
        or estimate.away.rank_value is None
        or estimate.home.recent_points_per_game is None
        or estimate.away.recent_points_per_game is None
    ):
        estimate.source = STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED
        estimate.source_reason = "自动分档缺少可解析排名或近况结果，无法稳定生成正式动态广义实力关系。"
    else:
        estimate.source = STRENGTH_SOURCE_AUTO_ESTIMATED
        estimate.source_reason = "档位由排名、近况、阵容、赛程、战意、人气和场地适应性辅助估算。"
    filled = StrengthContext(
        home_grade=existing.home_grade or estimate.home.grade,
        away_grade=existing.away_grade or estimate.away.grade,
        static_gap=existing.static_gap or _gap_label_value(estimate.static_gap_value),
        dynamic_adjustment=existing.dynamic_adjustment or (
            f"自动估算动态差={estimate.dynamic_gap_value:g}档；"
            f"主队components={estimate.home.components}；客队components={estimate.away.components}"
        ),
        final_gap=existing.final_gap or estimate.final_gap_label,
        original_distribution=existing.original_distribution or estimate.original_distribution,
        theoretical_psychological_interval=existing.theoretical_psychological_interval or estimate.theoretical_psychological_interval,
        theoretical_home_odds_range=existing.theoretical_home_odds_range or estimate.theoretical_home_odds_range,
        theoretical_draw_odds_reference=existing.theoretical_draw_odds_reference or estimate.theoretical_draw_odds_reference,
        theoretical_away_odds_reference=existing.theoretical_away_odds_reference or estimate.theoretical_away_odds_reference,
    )
    return filled, estimate
