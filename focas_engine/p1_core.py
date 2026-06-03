from __future__ import annotations

from collections import Counter
from typing import Optional

from .models import (
    MatchContext,
    NaturalPull,
    OriginalBookMode,
    OriginalDistribution,
    P1CoreResult,
    P1DirectionProfile,
    P1MainlineHypothesis,
    P1MisreadBlock,
    StrengthContext,
)
from .strength import grade_to_score

DIRECTIONS = ("主胜", "平局", "客胜")
PULL_RANK = {"弱": 0, "中": 1, "强": 2, None: 0, "未知": 0}


def _pull_by_direction(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {p.direction: p for p in pulls}


def _pull_strength(pulls: dict[str, NaturalPull], direction: str) -> str:
    return pulls.get(direction).strength if pulls.get(direction) and pulls[direction].strength else "未知"


def _strength_gap(strength: StrengthContext) -> int:
    h = grade_to_score(strength.home_grade)
    a = grade_to_score(strength.away_grade)
    if h is None or a is None:
        return 0
    return h - a


def _match_text(match: MatchContext, book_mode: OriginalBookMode) -> str:
    return " ".join(str(x) for x in (
        match.competition,
        match.stage,
        match.match_type,
        match.attention_level,
        book_mode.mode,
        book_mode.reason,
        book_mode.key_odds_to_watch,
        book_mode.easiest_misread,
    ) if x)


def _first_eye_direction(pulls: dict[str, NaturalPull]) -> Optional[str]:
    first = [d for d, p in pulls.items() if p.first_eye_direction]
    if len(first) == 1:
        return first[0]
    if len(first) > 1:
        ranked = sorted(first, key=lambda d: PULL_RANK.get(_pull_strength(pulls, d), 0), reverse=True)
        return ranked[0]
    ranked = sorted(DIRECTIONS, key=lambda d: PULL_RANK.get(_pull_strength(pulls, d), 0), reverse=True)
    return ranked[0] if ranked else None


def _distribution_type(match: MatchContext, strength: StrengthContext, pulls: dict[str, NaturalPull], book_mode: OriginalBookMode) -> str:
    gap = _strength_gap(strength)
    mode_text = _match_text(match, book_mode)
    home_pull = PULL_RANK.get(_pull_strength(pulls, "主胜"), 0)
    draw_pull = PULL_RANK.get(_pull_strength(pulls, "平局"), 0)
    away_pull = PULL_RANK.get(_pull_strength(pulls, "客胜"), 0)

    if "胜负双分" in mode_text:
        return "胜负双分"
    if "缓冲" in mode_text:
        return "缓冲分布"
    if "逆分布" in mode_text:
        return "逆分布"
    if "中庸" in mode_text or "强强" in mode_text:
        return "中庸分布"

    if match.neutral_venue or any(k in mode_text for k in ("决赛", "半决赛", "淘汰", "单回合")):
        if abs(gap) <= 1 or draw_pull >= 1:
            return "中庸分布 / 杯赛压缩"

    if gap >= 2 and home_pull >= away_pull:
        return "顺分布"
    if gap <= -1 and away_pull >= home_pull:
        return "客向顺分布"
    if gap >= 1 and away_pull >= home_pull:
        return "逆分布"
    if gap <= 0 and home_pull >= away_pull + 1:
        return "逆分布"
    if max(home_pull, draw_pull, away_pull) - min(home_pull, draw_pull, away_pull) <= 1:
        return "中庸分布"
    return "缓冲分布"


def _direction_distribution_strength(direction: str, gap: int, pulls: dict[str, NaturalPull], match: MatchContext) -> str:
    pull = PULL_RANK.get(_pull_strength(pulls, direction), 0)
    score = pull
    if direction == "主胜":
        score += 1 if gap >= 1 else -1 if gap <= -2 else 0
        if match.neutral_venue or match.real_home_away is False:
            score -= 0.3
    elif direction == "客胜":
        score += 1 if gap <= -1 else -1 if gap >= 2 else 0
    else:
        if abs(gap) <= 1:
            score += 1
        if match.neutral_venue:
            score += 0.3
        text = " ".join(str(x) for x in (match.stage, match.match_type) if x)
        if any(k in text for k in ("决赛", "半决赛", "淘汰", "单回合")):
            score += 0.3

    if score >= 3:
        return "强"
    if score >= 1.3:
        return "中"
    return "弱"


def _confidence_carrying(direction: str, original_strength: str, pulls: dict[str, NaturalPull]) -> str:
    p = pulls.get(direction)
    if original_strength == "强" and p and (p.easy_to_receive or p.first_eye_direction):
        return "足"
    if original_strength == "强":
        return "中高"
    if original_strength == "中":
        return "中"
    return "弱"


def _dispersion_support(direction: str, profiles_pre: dict[str, str], pulls: dict[str, NaturalPull]) -> str:
    others = [d for d in DIRECTIONS if d != direction]
    points = 0
    for d in others:
        if profiles_pre.get(d) == "强":
            points += 2
        elif profiles_pre.get(d) == "中":
            points += 1
        p = pulls.get(d)
        if p and p.easy_to_receive:
            points += 0.5
    if points >= 3:
        return "强"
    if points >= 1.5:
        return "中"
    return "弱"


def _expected_board_style(direction: str, confidence: str, dispersion: str, original_strength: str) -> tuple[str, str, bool]:
    """Return expected style, low-odds decrease meaning, can_bear_raise."""
    if confidence in {"足", "中高"} and dispersion in {"强", "中"}:
        return "中庸承接 / 顶高过渡可解释", "压低多为赔付修正或保护备选，不可机械等同主线确认", True
    if confidence in {"足", "中高"} and dispersion == "弱":
        return "实盘 / 降低赔付优先", "压低更可能是降低赔付；若反向抬高需检查是否暴露风险", False
    if confidence == "中" and dispersion in {"强", "中"}:
        return "中庸盘 / 过渡盘", "压低可能是风险修正，也可能是制造信心，需要公司确认", True
    if original_strength == "弱":
        return "韬盘 / 拉低营造备选", "自然信心弱时压低可能只是拉低营造或制造分流信心，不可直接认定保护", False
    return "观察盘 / 动机未确认", "压低含义未确认，需要回到表内位置和公司分工", False


def _distribution_role(direction: str, distribution_type: str, confidence: str, dispersion: str) -> str:
    if distribution_type == "胜负双分":
        return "两端分流主项" if direction in {"主胜", "客胜"} else "可能被胜负两端分流"
    if "平负合力" in distribution_type:
        return "合力主项" if direction in {"平局", "客胜"} else "被平负合力遮蔽备选"
    if "胜平合力" in distribution_type:
        return "合力主项" if direction in {"主胜", "平局"} else "被胜平合力遮蔽备选"
    if direction == "平局" and "中庸" in distribution_type:
        return "平赔分散核心"
    if confidence in {"足", "中高"}:
        return "原始承接项"
    if dispersion in {"强", "中"}:
        return "分散工具备选"
    return "弱承接 / 需营造项"


def _easiest_to_disperse(profiles: list[P1DirectionProfile]) -> Optional[str]:
    if not profiles:
        return None
    ranked = sorted(
        profiles,
        key=lambda p: (
            2 if p.distribution_role in {"分散工具备选", "平赔分散核心"} else 1 if "合力" in p.distribution_role else 0,
            2 if p.dispersion_support == "强" else 1 if p.dispersion_support == "中" else 0,
        ),
        reverse=True,
    )
    return ranked[0].direction


def _hypothesis(direction: str, profile: P1DirectionProfile) -> P1MainlineHypothesis:
    if direction == "主胜":
        support = ["主队广义实力或人气能够承载主赔", "平局/客胜至少一项有分散力", "主赔不能越过心理区间上沿"]
    elif direction == "平局":
        support = ["双方档位差不能过大", "平局自然拉力不能为弱", "胜负两端需要能分散平赔"]
    else:
        support = ["客队广义实力或动态修正能承载客赔", "主胜/平局能构成分散或遮蔽", "客赔不能只是高回报无承载"]

    questions = [
        f"现实赔率是否符合 {profile.expected_board_style}？",
        f"该方向信心承载={profile.confidence_carrying}，是否足以解释赔率抬高或压低？",
        f"其他两项分散支持={profile.dispersion_support}，是否足以让机构这样开盘有意义？",
    ]
    return P1MainlineHypothesis(
        direction=direction,
        expected_bookmaker_goal=(
            f"若{direction}是结构主线，机构应围绕该方向做{profile.expected_board_style}，"
            f"并利用其他方向完成分散/遮蔽，而不是无动机地移动赔率。"
        ),
        required_support=support,
        reality_check_questions=questions,
    )


def _misread_blocks(profiles: list[P1DirectionProfile]) -> list[P1MisreadBlock]:
    by_dir = {p.direction: p for p in profiles}
    blocks = [
        P1MisreadBlock(
            pattern="主赔升 = 主胜不利",
            blocked_reason="必须先看主胜信心承载和其他两项分散力；若主胜可承载且分散有效，主赔抬高只能理解为未打掉信心/顶高承接边界，不能说成机构给主胜制造信心。",
            affected_directions=["主胜"],
        ),
        P1MisreadBlock(
            pattern="主赔降 = 主胜有利",
            blocked_reason="主胜自然信心弱时，压低主赔可能是拉低营造或分流工具，不能直接当作保护。",
            affected_directions=["主胜"],
        ),
        P1MisreadBlock(
            pattern="平赔低 = 平局保护",
            blocked_reason="平局信心弱时，低平可能只是给胜/负方向制造分洪区；需看平局自然拉力与胜负分散结构。",
            affected_directions=["平局"],
        ),
        P1MisreadBlock(
            pattern="客赔低 = 客胜确认",
            blocked_reason="客胜自然信心不足时，压低客赔可能是拉低营造，不等于客胜主线。",
            affected_directions=["客胜"],
        ),
        P1MisreadBlock(
            pattern="确认不足 = 排除",
            blocked_reason="确认不足只能降级为未确认；只有赔率动作、表内区间、自然拉力和公司合力共同不利，才能排除主线资格。",
            affected_directions=list(DIRECTIONS),
        ),
    ]
    # Add a dynamic note for directions that can bear an odds raise.
    for d, p in by_dir.items():
        if p.can_bear_odds_raise:
            blocks.append(P1MisreadBlock(
                pattern=f"{d}赔率抬高必然不利",
                blocked_reason=f"{d}当前信心承载={p.confidence_carrying}，分散支持={p.dispersion_support}，具备承载抬高回报的边界；这只解除机械不利，不能直接加为主线确认，必须继续看表内区间和公司合力。",
                affected_directions=[d],
            ))
    return blocks


def build_p1_core(
    *,
    match: MatchContext,
    strength: StrengthContext,
    pulls: list[NaturalPull],
    book_mode: OriginalBookMode,
    original_distribution: OriginalDistribution | None = None,
) -> P1CoreResult:
    """Executable P1 layer.

    This module does not output a match result. It builds the original distribution,
    confidence-carrying and board-style constraints that later bookmaker-motive
    logic must obey.
    """
    pull_map = _pull_by_direction(pulls)
    gap = _strength_gap(strength)
    distribution_type = (
        original_distribution.distribution_type
        if original_distribution is not None
        else _distribution_type(match, strength, pull_map, book_mode)
    )
    first_eye = (
        original_distribution.first_eye_direction
        if original_distribution is not None
        else _first_eye_direction(pull_map)
    )

    if original_distribution is not None:
        pre_strength = {
            "主胜": original_distribution.home_pressure,
            "平局": original_distribution.draw_pressure,
            "客胜": original_distribution.away_pressure,
        }
    else:
        pre_strength = {
            d: _direction_distribution_strength(d, gap, pull_map, match)
            for d in DIRECTIONS
        }

    profiles: list[P1DirectionProfile] = []
    for d in DIRECTIONS:
        original_strength = pre_strength[d]
        confidence = _confidence_carrying(d, original_strength, pull_map)
        dispersion = _dispersion_support(d, pre_strength, pull_map)
        style, low_meaning, can_raise = _expected_board_style(d, confidence, dispersion, original_strength)
        role = _distribution_role(d, distribution_type, confidence, dispersion)
        notes = [
            f"P1原始分布强度={original_strength}",
            f"自然拉力={_pull_strength(pull_map, d)}",
            f"档位差={gap}",
        ]
        if d == first_eye:
            notes.append("该方向是大众第一眼方向备选，赔率动作需先判断承载而非机械打击。")
        profiles.append(P1DirectionProfile(
            direction=d,
            natural_pull=_pull_strength(pull_map, d),
            original_distribution_strength=original_strength,
            confidence_carrying=confidence,
            dispersion_support=dispersion,
            expected_board_style=style,
            distribution_role=role,
            can_bear_odds_raise=can_raise,
            low_odds_decrease_meaning=low_meaning,
            notes=notes,
        ))

    easiest = _easiest_to_disperse(profiles)
    hypotheses = [_hypothesis(p.direction, p) for p in profiles]
    counter = Counter(p.confidence_carrying for p in profiles)
    notes = [
        "P1底层逻辑已运行：后续赔率动作必须回到独立原始分布、信心承载、分散有效性和预期开盘风格解释；赔率抬高只能检验承载边界，不能被表述为机构给该方向信心。",
        f"信心承载分布={dict(counter)}",
        "P1不直接给赛果；它只限制后续公司动机链哪些解释成立、哪些机械误读必须拦截。",
    ]
    if first_eye:
        notes.append(f"大众第一眼方向备选={first_eye}。")
    if easiest:
        notes.append(f"最容易承担分散功能的方向备选={easiest}。")
    if original_distribution is not None:
        notes.append("P1 已消费赔率读取前生成的独立原始分布，不允许由赔率动作反向改写该分布。")

    return P1CoreResult(
        distribution_type=distribution_type,
        first_eye_direction=first_eye,
        easiest_to_disperse_direction=easiest,
        profiles=profiles,
        hypotheses=hypotheses,
        misread_blocks=_misread_blocks(profiles),
        notes=notes,
    )


def profile_by_direction(p1: Optional[P1CoreResult]) -> dict[str, P1DirectionProfile]:
    if not p1:
        return {}
    return {p.direction: p for p in p1.profiles}
