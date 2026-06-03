from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .models import MatchContext, NaturalPull, OriginalBookMode, OriginalDistribution, StrengthContext
from .event_context import is_knockout_like_context
from .strength import grade_to_score


@dataclass
class ModeOption:
    mode: str
    score: float
    reason: str
    key_odds_to_watch: str
    easiest_misread: str
    source_tags: list[str] = field(default_factory=list)


@dataclass
class OriginalModeEstimateResult:
    primary_mode: str
    primary_reason: str
    key_odds_to_watch: str
    easiest_misread: str
    options: list[ModeOption]
    source_classification: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_STRONG_GRADES = {"人强", "普强", "准强"}


def _contains(text: Optional[str], keywords: Iterable[str]) -> bool:
    if not text:
        return False
    raw = str(text)
    return any(k in raw for k in keywords)


def _pull_map(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {p.direction: p for p in pulls}


def _pull_strength(pulls: dict[str, NaturalPull], direction: str) -> str:
    return (pulls.get(direction).strength if pulls.get(direction) else None) or "未知"


def _is_first_eye(pulls: dict[str, NaturalPull], direction: str) -> bool:
    p = pulls.get(direction)
    return bool(p and p.first_eye_direction)


def _gap_steps(strength: StrengthContext) -> Optional[int]:
    h = grade_to_score(strength.home_grade)
    a = grade_to_score(strength.away_grade)
    if h is None or a is None:
        return None
    return h - a


def _both_strong(strength: StrengthContext) -> bool:
    return (strength.home_grade in _STRONG_GRADES) and (strength.away_grade in _STRONG_GRADES)


def _match_text(match: MatchContext) -> str:
    parts = [match.stage, match.match_type, match.competition, match.attention_level]
    return " ".join(str(p) for p in parts if p)


def _option(
    *,
    mode: str,
    score: float,
    reason: str,
    key_odds_to_watch: str,
    easiest_misread: str,
    source_tags: list[str],
) -> ModeOption:
    return ModeOption(
        mode=mode,
        score=round(score, 3),
        reason=reason,
        key_odds_to_watch=key_odds_to_watch,
        easiest_misread=easiest_misread,
        source_tags=source_tags,
    )


def estimate_original_mode(
    *,
    match: MatchContext,
    strength: StrengthContext,
    pulls: list[NaturalPull],
    original_distribution: OriginalDistribution | None = None,
) -> OriginalModeEstimateResult:
    """
    Executable P1 mode linker.

    This is not a prediction engine. It turns the completed basic context,
    broad-strength ladder and three natural pulls into auditable original-book
    mode options, so the pipeline no longer depends on a manually filled
    label such as “顺分布”.
    """
    options: list[ModeOption] = []
    warnings: list[str] = []
    pmap = _pull_map(pulls)
    gap = _gap_steps(strength)
    text = _match_text(match)

    home_pull = _pull_strength(pmap, "主胜")
    draw_pull = _pull_strength(pmap, "平局")
    away_pull = _pull_strength(pmap, "客胜")

    if original_distribution is not None:
        options.append(_option(
            mode=original_distribution.distribution_type,
            score=2.0,
            reason=(
                f"赔率读取前的独立原始分布层判定为 {original_distribution.distribution_type}；"
                f"主胜/平局/客胜原始压力="
                f"{original_distribution.home_pressure}/{original_distribution.draw_pressure}/{original_distribution.away_pressure}。"
            ),
            key_odds_to_watch="后续赔率动作必须与原始压力对照解释，不能由赔率反向改写原始分布。",
            easiest_misread="原始压力强不等于方向确认；原始压力弱也不等于方向排除。",
            source_tags=["original_distribution"],
        ))

    if gap is None:
        warnings.append("无法从广义实力档位计算档位差，原书模式挂接置信度下降。")

    if match.neutral_venue:
        options.append(_option(
            mode="中立场盘",
            score=2.2,
            reason="比赛被标记为中立场，真实主客属性弱化，主客场因素不能按普通联赛主客场直接解释。",
            key_odds_to_watch="主赔是否仍承担真实主项信心；平赔是否因中立场被抬升为自然承接；客赔是否获得额外承载。",
            easiest_misread="不能把名义主队的低赔直接理解为真实主场优势，也不能把中立场下的平赔变化机械理解为保护。",
            source_tags=["match.neutral_venue"],
        ))

    if _contains(text, ("决赛", "final", "Final")):
        options.append(_option(
            mode="决赛盘",
            score=2.3,
            reason="赛事阶段包含决赛语境，单场关注度、谨慎心理和平局/加时叙事会改变三项原始分布。",
            key_odds_to_watch="平赔是否被合理使用；胜负两端是否形成双分；低赔方是否仍有足够信心承载。",
            easiest_misread="不能把决赛里的低赔方按普通联赛强弱盘处理，决赛会压缩实力差并提高平局自然受注。",
            source_tags=["match.stage", "match.match_type"],
        ))

    if is_knockout_like_context(match):
        score = 1.2 + (0.4 if match.single_leg else 0.0)
        options.append(_option(
            mode="杯赛 / 淘汰赛压缩盘",
            score=score,
            reason="赛事含杯赛、淘汰赛或单回合属性，战意明确，但常规主客和联赛排名权重需要降级。",
            key_odds_to_watch="平赔是否承担加时/谨慎分布；低赔方是否在表内合理承接；高赔方是否被低估为单纯陪衬。",
            easiest_misread="不能用联赛排名差直接替代杯赛广义实力差。",
            source_tags=["match_type", "single_leg"],
        ))

    if gap is not None and gap >= 2:
        options.append(_option(
            mode="顺分布 / 强弱盘 / 胜赔手法",
            score=2.0 + min(gap, 4) * 0.2,
            reason=(
                f"主队广义实力高于客队约 {gap} 档，且主胜自然拉力为{home_pull}，"
                "市场原始分布容易向主项集中。"
            ),
            key_odds_to_watch="主赔是否处在表内合理承接位；平负是否形成有效分散；主赔抬高是否仍有信心承载。",
            easiest_misread="不能把主赔抬高机械理解为主胜不利，也不能反向说成机构给主胜信心；若主项信心充足且平负分散有效，抬高只属于未打掉信心/顶高承接边界。",
            source_tags=["strength_gap", "home_pull"],
        ))
    elif gap is not None and gap <= -2:
        options.append(_option(
            mode="客向顺分布 / 平负合力备选",
            score=2.0 + min(abs(gap), 4) * 0.2,
            reason=(
                f"客队广义实力高于主队约 {abs(gap)} 档，客胜自然拉力为{away_pull}，"
                "客项可能不是普通高赔冷门，而是需要判断平负合力或客低赔承接。"
            ),
            key_odds_to_watch="客赔是否落入客低赔表内合理区间；主赔和平赔是否共同遮蔽或分散客胜。",
            easiest_misread="不能因为客队是客场就默认客胜不利；要先判断客赔在对应体系中的低中高水位置。",
            source_tags=["strength_gap", "away_pull"],
        ))
    elif gap is not None and abs(gap) <= 1 and _both_strong(strength):
        options.append(_option(
            mode="强强对话 / 中庸分布",
            score=2.7,
            reason=(
                f"主客档位为 {strength.home_grade} vs {strength.away_grade}，档位差不超过 1 档且双方均达到准强以上，"
                "市场通常不是单项集中，而是胜平负均有承接。"
            ),
            key_odds_to_watch="平赔是否被充分使用；胜负两端是否双向分散；低赔方是否只是名义优势而非实盘确认。",
            easiest_misread="不能把强强对话中的某一端低赔直接理解为单边强信心，必须先看平赔分散作用是否被主动使用。",
            source_tags=["strength.home_grade", "strength.away_grade", "gap"],
        ))
    elif gap is not None and abs(gap) <= 1:
        options.append(_option(
            mode="中庸分布",
            score=1.8,
            reason=(
                f"主客档位差约 {gap} 档，双方广义实力接近，原始市场没有天然单边锚点。"
            ),
            key_odds_to_watch="三项赔率是否维持均衡；平赔是否成为核心分散点；胜负是否被做成错位分流。",
            easiest_misread="不能只看最低赔方向；同档或近似同档比赛需要先看三项组合赔面。",
            source_tags=["strength_gap"],
        ))

    if home_pull == "强" and draw_pull in {"中", "强"}:
        options.append(_option(
            mode="胜平合力 / 信心区间",
            score=1.6 + (0.3 if _is_first_eye(pmap, "主胜") else 0.0),
            reason="主胜具备自然拉力，平局也有承接空间，胜平可能共同承担信心区间或分散任务。",
            key_odds_to_watch="主赔与平赔是否同步形成低位/中位合力；客赔是否被遮蔽、韬开或高阻。",
            easiest_misread="不能把平赔回收简单等同于平局真实保护，它可能是在配合主赔形成胜平合力。",
            source_tags=["natural_pull.home", "natural_pull.draw"],
        ))

    if away_pull == "强" and draw_pull in {"中", "强"}:
        options.append(_option(
            mode="平负合力 / 客胜信心区间",
            score=1.6 + (0.3 if _is_first_eye(pmap, "客胜") else 0.0),
            reason="客胜具备自然拉力，平局也有承接空间，平负可能共同承担信心区间或分散任务。",
            key_odds_to_watch="客赔与平赔是否共同回收；主赔是否被抬成承接或阻力；平负合力是否足以遮蔽主胜。",
            easiest_misread="不能把客赔低或平赔低单独视为客胜确认，必须看平负两端是否形成有效合力。",
            source_tags=["natural_pull.away", "natural_pull.draw"],
        ))

    if home_pull in {"强", "中"} and away_pull in {"强", "中"} and draw_pull in {"弱", "中"}:
        options.append(_option(
            mode="胜负双分",
            score=1.2 + (0.3 if draw_pull == "弱" else 0.0),
            reason="胜负两端都有受注承载，平局不是唯一自然分散点，存在胜负双向分流条件。",
            key_odds_to_watch="平赔是否被顶高或失去保护；胜负两端是否被做成对冲分流。",
            easiest_misread="不能看到两端都有拉力就说三项都保留，平赔是否被主动牺牲要单独判断。",
            source_tags=["natural_pull.home", "natural_pull.away", "natural_pull.draw"],
        ))

    # Buffer distribution: both sides carry visible flaws or all pulls are medium-like.
    if {home_pull, draw_pull, away_pull}.issubset({"中", "弱", "未知"}) or _contains(
        (match.home.attack_state if match.home else "") + (match.away.attack_state if match.away else "") +
        (match.home.defense_state if match.home else "") + (match.away.defense_state if match.away else ""),
        ("低迷", "不稳", "问题", "漏洞", "乏力"),
    ):
        options.append(_option(
            mode="缓冲分布",
            score=1.1,
            reason="两队至少存在状态、攻防或拉力上的互相缓冲条件，单项赔率动作需要先判断能否被缺点抵消。",
            key_odds_to_watch="最低赔方向是否真的无法缓冲；平赔是否承担主力分散；高赔项是否只是被赔率制造。",
            easiest_misread="不能只因某队排名或低赔占优就忽略另一侧缺点对受注分布的缓冲作用。",
            source_tags=["team_state", "natural_pull"],
        ))

    if not options:
        options.append(_option(
            mode="中庸分布",
            score=0.5,
            reason="缺少足够条件挂接更细模式，先按中庸分布保守处理。",
            key_odds_to_watch="三项组合赔面、平赔分散作用、低赔方向是否越界。",
            easiest_misread="不能在模式证据不足时强行套用强弱盘或强强对话。",
            source_tags=["fallback"],
        ))
        warnings.append("原书模式证据不足，已使用保守中庸分布备选。")

    options.sort(key=lambda c: c.score, reverse=True)
    top = options[:3]
    primary_mode = " / ".join(c.mode for c in top if c.score >= max(0.8, top[0].score - 0.7))
    primary_reason = "；".join(c.reason for c in top[:2])
    key_watch = "；".join(dict.fromkeys(c.key_odds_to_watch for c in top[:3]))
    misread = "；".join(dict.fromkeys(c.easiest_misread for c in top[:3]))

    return OriginalModeEstimateResult(
        primary_mode=primary_mode,
        primary_reason=primary_reason,
        key_odds_to_watch=key_watch,
        easiest_misread=misread,
        options=options,
        source_classification=[
            "原书明示：模式名称沿用《欧赔核心思维》的可调用术语。",
            "原书推导：依据广义实力、三项自然拉力和独立原始分布挂接本场模式。",
            "项目规则：模式只限定后续观察重点，不直接输出赛果。",
            "临场判断：实际赔率动作仍须在返还率体系识别、对应骨架表路由和现代骨架查表后解释。",
        ],
        warnings=warnings,
    )


def fill_original_book_mode(
    existing: OriginalBookMode,
    *,
    match: MatchContext,
    strength: StrengthContext,
    pulls: list[NaturalPull],
    original_distribution: OriginalDistribution | None = None,
) -> tuple[OriginalBookMode, OriginalModeEstimateResult]:
    """
    Fill missing OriginalBookMode fields. User-provided fields always win.
    """
    estimate = estimate_original_mode(
        match=match,
        strength=strength,
        pulls=pulls,
        original_distribution=original_distribution,
    )
    filled = OriginalBookMode(
        mode=existing.mode or estimate.primary_mode,
        reason=existing.reason or estimate.primary_reason,
        key_odds_to_watch=existing.key_odds_to_watch or estimate.key_odds_to_watch,
        easiest_misread=existing.easiest_misread or estimate.easiest_misread,
        source_classification=existing.source_classification or estimate.source_classification,
    )
    return filled, estimate
