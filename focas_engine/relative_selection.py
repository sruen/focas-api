from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .models import (
    CompanyRelationResult,
    DirectionJudgement,
    MatchContext,
    MotiveReading,
    NaturalPull,
    OpeningMotiveReading,
    OriginalBookMode,
    OriginalDistribution,
    P1CoreResult,
    RelativeSelectionResult,
    RelativeSelectionScore,
    StrengthContext,
    TableLookupResult,
)
from .strength import grade_to_score
from .p1_core import profile_by_direction
from .original_distribution import pressure_by_direction
from .odds_system import normalize_company
from .event_context import is_knockout_like_context

PULL_SCORE = {"强": 2.0, "中": 1.0, "弱": -1.0, "未知": 0.0, None: 0.0}
DIRECTIONS = ("主胜", "平局", "客胜")


def _pull_by_direction(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {p.direction: p for p in pulls}


def _judgement_by_direction(judgements: list[DirectionJudgement]) -> dict[str, DirectionJudgement]:
    return {j.direction: j for j in judgements}


def _strength_gap(strength: StrengthContext) -> int:
    h = grade_to_score(strength.home_grade)
    a = grade_to_score(strength.away_grade)
    if h is None or a is None:
        return 0
    return h - a


def _add(scores: dict[str, float], reasons: dict[str, list[str]], direction: str, amount: float, reason: str) -> None:
    scores[direction] += amount
    sign = "+" if amount >= 0 else ""
    reasons[direction].append(f"{sign}{amount:.2f}｜{reason}")


def _apply_natural_pull(scores: dict[str, float], reasons: dict[str, list[str]], pulls: list[NaturalPull]) -> None:
    by_dir = _pull_by_direction(pulls)
    for direction in DIRECTIONS:
        p = by_dir.get(direction)
        strength = p.strength if p else "未知"
        amount = PULL_SCORE.get(strength, 0.0)
        _add(scores, reasons, direction, amount, f"自然拉力={strength}")
        if p and p.first_eye_direction:
            _add(scores, reasons, direction, 0.25, "大众第一眼方向，具备自然受注承载")
        if p and p.easy_to_receive:
            _add(scores, reasons, direction, 0.20, "容易受注，具备分布承接能力")


def _apply_original_distribution(
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    original_distribution: OriginalDistribution | None,
) -> None:
    if original_distribution is None:
        return
    for direction, pressure in pressure_by_direction(original_distribution).items():
        if pressure == "强":
            _add(scores, reasons, direction, 0.40, "原始分布压力强：只增加相对承载分，不直接确认")
        elif pressure == "中":
            _add(scores, reasons, direction, 0.15, "原始分布压力中：保留相对承载")
        else:
            _add(scores, reasons, direction, -0.25, "原始分布压力弱：只降低相对强度，不构成不利排除")
        if original_distribution.dispersion_available.get(direction):
            _add(scores, reasons, direction, 0.10, "原始分布显示可承担分流：只作相对比较")


def _apply_strength_gap(scores: dict[str, float], reasons: dict[str, list[str]], strength: StrengthContext, match: MatchContext) -> None:
    gap = _strength_gap(strength)
    if gap > 0:
        _add(scores, reasons, "主胜", min(gap, 4) * 0.45, f"广义实力主队高 {gap} 档")
        _add(scores, reasons, "客胜", -min(gap, 4) * 0.30, f"广义实力客队低 {gap} 档")
    elif gap < 0:
        _add(scores, reasons, "客胜", min(abs(gap), 4) * 0.45, f"广义实力客队高 {abs(gap)} 档")
        _add(scores, reasons, "主胜", -min(abs(gap), 4) * 0.30, f"广义实力主队低 {abs(gap)} 档")
    else:
        _add(scores, reasons, "平局", 0.45, "广义实力近似同档，平局承接增强")

    if match.neutral_venue:
        _add(scores, reasons, "平局", 0.25, "中立场削弱真实主客优势，平局自然承接增强")
    if is_knockout_like_context(match):
        _add(scores, reasons, "平局", 0.25, "杯赛/淘汰/单回合语境压缩常规实力差")


def _apply_original_mode(scores: dict[str, float], reasons: dict[str, list[str]], mode: OriginalBookMode) -> None:
    text = " ".join(str(x) for x in (mode.mode, mode.reason, mode.key_odds_to_watch, mode.easiest_misread) if x)
    if "胜平合力" in text or "信心区间" in text and "胜" in text:
        _add(scores, reasons, "主胜", 0.55, "原书模式提示胜平合力/主项信心区间")
        _add(scores, reasons, "平局", 0.35, "原书模式提示胜平合力，平局参与分散")
        _add(scores, reasons, "客胜", -0.35, "胜平合力对客项形成相对遮蔽")
    if "平负合力" in text or "客胜信心区间" in text:
        _add(scores, reasons, "客胜", 0.55, "原书模式提示平负合力/客项信心区间")
        _add(scores, reasons, "平局", 0.35, "原书模式提示平负合力，平局参与分散")
        _add(scores, reasons, "主胜", -0.35, "平负合力对主项形成相对遮蔽")
    if "胜负双分" in text:
        _add(scores, reasons, "主胜", 0.35, "原书模式提示胜负双分")
        _add(scores, reasons, "客胜", 0.35, "原书模式提示胜负双分")
        _add(scores, reasons, "平局", -0.45, "胜负双分下平局可能被两端分流")
    if "强强对话" in text or "中庸分布" in text:
        _add(scores, reasons, "平局", 0.35, "强强/中庸分布下平赔分散作用需要被重视")
    if "顺分布" in text or "强弱盘" in text or "胜赔手法" in text:
        if "客向" not in text and "平负" not in text:
            _add(scores, reasons, "主胜", 0.35, "顺分布/强弱盘下主项具备原始承接")
    if "客向" in text:
        _add(scores, reasons, "客胜", 0.35, "客向顺分布下客项具备原始承接")
    if "决赛盘" in text or "中立场盘" in text:
        _add(scores, reasons, "平局", 0.20, "决赛/中立场盘提高平局自然承接")


def _apply_p1_core(
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    p1_core: P1CoreResult | None,
) -> None:
    if not p1_core:
        return
    profiles = profile_by_direction(p1_core)
    for direction, profile in profiles.items():
        if profile.confidence_carrying in {"足", "中高"}:
            _add(scores, reasons, direction, 0.35, f"P1信心承载={profile.confidence_carrying}")
        elif profile.confidence_carrying == "弱":
            _add(scores, reasons, direction, -0.30, "P1信心承载弱")

        if profile.can_bear_odds_raise:
            _add(scores, reasons, direction, 0.00, "P1允许承载抬高回报：只解除机械不利，不直接加主线分")

        if profile.distribution_role in {"原始承接项", "合力主项"}:
            _add(scores, reasons, direction, 0.30, f"P1分布角色={profile.distribution_role}")
        elif "被" in profile.distribution_role or "弱承接" in profile.distribution_role:
            _add(scores, reasons, direction, -0.20, f"P1分布角色={profile.distribution_role}")
        elif "分散" in profile.distribution_role:
            _add(scores, reasons, direction, 0.10, f"P1可作为分散角色={profile.distribution_role}")

    if p1_core.distribution_type == "胜负双分":
        _add(scores, reasons, "平局", -0.25, "P1分布类型=胜负双分，平局相对受压")
    if "中庸" in p1_core.distribution_type:
        _add(scores, reasons, "平局", 0.20, f"P1分布类型={p1_core.distribution_type}，平赔分散价值提升")


def _apply_table_and_motives(
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    table_results: list[TableLookupResult],
    motives: list[MotiveReading],
) -> None:
    company_positive_support = defaultdict(int)
    for r in motives:
        if normalize_company(r.company) not in {"William", "Ladbrokes"}:
            continue
        if r.adverse_evidence:
            _add(scores, reasons, r.direction, -0.65, f"{r.company} 形成不利证据：{r.motive_type}")
            continue
        if "保护" in r.motive_type or "风险修正" in r.motive_type:
            _add(scores, reasons, r.direction, 0.20, f"{r.company} {r.motive_type}，只作风险/赔付修正加权")
            company_positive_support[r.direction] += 1
        elif "顶高承接" in r.motive_type:
            _add(scores, reasons, r.direction, 0.00, f"{r.company} 顶高承接边界：未直接打击，但不能说成给信心")
        elif "维持承接" in r.motive_type:
            _add(scores, reasons, r.direction, 0.00, f"{r.company} 维持承接：结构延续，不加主线分")
        elif "拉低营造" in r.motive_type:
            _add(scores, reasons, r.direction, -0.10, f"{r.company} 拉低营造，需防止只是分流工具")

    for direction, count in company_positive_support.items():
        if count >= 2:
            _add(scores, reasons, direction, 0.20, "至少两家公司对该方向形成风险/赔付修正支持；仍不是单独主线确认")

    for t in table_results:
        if t.table_axis != "home":
            continue
        if t.direction != "主低赔":
            continue
        if t.direction == "主低赔":
            direction = "主胜"
        elif t.direction == "客低赔":
            direction = "客胜"
        else:
            continue
        if t.lookup_status == "TABLE_READ_CONFIRMED":
            if t.deviation == "表内":
                _add(scores, reasons, direction, 0.20, f"{t.company} 低赔方向表内归位")
            elif "高于" in t.deviation:
                _add(scores, reasons, direction, -0.35, f"{t.company} 低赔方向高于表内上界")
            elif "低于" in t.deviation:
                _add(scores, reasons, direction, 0.10, f"{t.company} 低赔方向低于表内下界，偏降低赔付")


def _apply_company_semantics(
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    company_semantics: CompanyRelationResult | None,
) -> None:
    if not company_semantics:
        return
    for d in company_semantics.confirmed_directions:
        _add(scores, reasons, d, 0.55, f"双公司语义确认：{company_semantics.relation_type}")
    for d in company_semantics.unconfirmed_directions:
        _add(scores, reasons, d, 0.00, "公司语义确认不足，只保留未确认状态，不增加结构方向分")
    for d in company_semantics.conflict_directions:
        _add(scores, reasons, d, -0.40, "公司语义冲突，降低相对主线强度")
    for d in company_semantics.adverse_pressure_directions:
        _add(scores, reasons, d, -0.35, "双公司语义存在不利压力，需与不利判定分开处理")

    if company_semantics.relation_type == "分工":
        # Cross handling usually means no single-company line should be over-trusted.
        for d in DIRECTIONS:
            _add(scores, reasons, d, -0.05, "公司关系为交叉/分工，单项确认降权")
    elif company_semantics.relation_type == "冲突":
        for d in DIRECTIONS:
            _add(scores, reasons, d, -0.10, "公司关系冲突，整体结构置信度降权")




def _apply_interval_audit(
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    interval_audit,
) -> None:
    if not interval_audit or not getattr(interval_audit, "ok", False):
        return
    for audit in getattr(interval_audit, "audits", []) or []:
        tags = set(getattr(audit, "semantic_tags", []) or [])
        prefix = f"{audit.company} 初赔区间审计：{audit.deviation_label}"
        if "抬胜" in tags:
            _add(scores, reasons, "主胜", -0.85, prefix + "，抬胜不按理论区间承接")
        if "负韬" in tags:
            _add(scores, reasons, "客胜", 0.50, prefix + "，负韬保留客胜韬开价值")
        if "拉平" in tags:
            _add(scores, reasons, "平局", 0.15, prefix + "，低平/拉平参与胜平合力，但需防止误封平")
        if "抬负" in tags:
            _add(scores, reasons, "客胜", -0.60, prefix + "，抬负可能造成客向过热或高估")
        if "胜韬" in tags:
            _add(scores, reasons, "主胜", 0.00, prefix + "，胜韬只解除机械排除，不增加主胜结构方向分")
        if "平负合力备选" in tags:
            _add(scores, reasons, "平局", 0.20, prefix + "，平负合力备选")
            _add(scores, reasons, "客胜", 0.20, prefix + "，平负合力备选")
        if "顺区间" in tags:
            d = getattr(audit, "opening_low_direction", "")
            if d in DIRECTIONS:
                _add(scores, reasons, d, 0.15, prefix + "，初赔与理论区间顺开")


def _apply_opening_motive_constraints(
    scores: dict[str, float],
    reasons: dict[str, list[str]],
    opening_motive_readings: list[OpeningMotiveReading],
    company_semantics: CompanyRelationResult | None,
) -> set[str]:
    """Return directions blocked by unresolved double-company opening lure.

    A fundamentals-driven opening lure is not an adverse exclusion. It is a
    second-stage consistency constraint: the same direction may return only
    after explicit William/Ladbrokes reversal confirmation.
    """
    lure_counts: dict[str, int] = defaultdict(int)
    confirmed = set(getattr(company_semantics, "confirmed_directions", []) or [])
    for reading in opening_motive_readings:
        if normalize_company(reading.company) not in {"William", "Ladbrokes"}:
            continue
        if reading.selection_constraint == "REQUIRE_REVERSAL_CONFIRMATION":
            lure_counts[reading.direction] += 1

    blocked: set[str] = set()
    for direction, count in lure_counts.items():
        if direction in confirmed:
            _add(
                scores,
                reasons,
                direction,
                0.00,
                "初赔存在利诱/过热候选，但后续 William / Ladbrokes 已形成反转确认；允许重新参与相对选择",
            )
        elif count >= 2:
            blocked.add(direction)
            _add(
                scores,
                reasons,
                direction,
                -3.00,
                "双公司初赔均利用基本面或主客场拉力形成利诱/过热候选，后续没有双公司反转确认；禁止仅凭基本面高分重新选回",
            )
        else:
            _add(
                scores,
                reasons,
                direction,
                -0.75,
                "单公司初赔存在利诱/过热候选，后续未形成双公司反转确认；降低相对结构强度",
            )
    return blocked


def select_relative_mainline(
    *,
    judgements: list[DirectionJudgement],
    strength: StrengthContext,
    pulls: list[NaturalPull],
    book_mode: OriginalBookMode,
    table_results: list[TableLookupResult],
    motive_readings: list[MotiveReading],
    match: MatchContext,
    p1_core: P1CoreResult | None = None,
    company_semantics: CompanyRelationResult | None = None,
    interval_audit=None,
    original_distribution: OriginalDistribution | None = None,
    opening_motive_readings: list[OpeningMotiveReading] | None = None,
) -> RelativeSelectionResult:
    """
    Second-stage selector for v0.4.

    It does not re-label weaker remaining directions as “adverse”.
    It chooses a single structural direction only after recording the explicit
    adverse exclusions and then scoring the remaining directions by broad
    strength, original distribution, table position and bookmaker motive chain.
    """
    jmap = _judgement_by_direction(judgements)
    adverse = [d for d in DIRECTIONS if jmap.get(d) and jmap[d].status == "不利"]
    scores = {d: 0.0 for d in DIRECTIONS}
    reasons: dict[str, list[str]] = defaultdict(list)

    for d in adverse:
        scores[d] = -999.0
        reasons[d].append("已被不利证据排除主线资格，不参与第二阶段相对选择。")

    _apply_natural_pull(scores, reasons, pulls)
    _apply_original_distribution(scores, reasons, original_distribution)
    _apply_strength_gap(scores, reasons, strength, match)
    _apply_original_mode(scores, reasons, book_mode)
    _apply_p1_core(scores, reasons, p1_core)
    _apply_table_and_motives(scores, reasons, table_results, motive_readings)
    _apply_company_semantics(scores, reasons, company_semantics)
    _apply_interval_audit(scores, reasons, interval_audit)
    blocked_by_opening_lure = _apply_opening_motive_constraints(
        scores,
        reasons,
        opening_motive_readings or [],
        company_semantics,
    )

    eligible = [d for d in DIRECTIONS if d not in adverse and d not in blocked_by_opening_lure]
    # If there are no explicit exclusions, this still returns a structural lean,
    # but the caller may decide whether to use it as final. v0.4 pipeline uses it
    # only when exactly one direction was explicitly adverse.
    ranked = sorted(eligible, key=lambda d: (scores[d], d), reverse=True)
    selected = ranked[0] if ranked else ""
    margin = (scores[ranked[0]] - scores[ranked[1]]) if len(ranked) >= 2 else 999.0
    confidence = "高" if margin >= 1.0 else "中" if margin >= 0.45 else "低"
    if not adverse and confidence == "高":
        confidence = "中"

    result_scores = []
    for d in DIRECTIONS:
        result_scores.append(RelativeSelectionScore(
            direction=d,
            score=round(scores[d], 3),
            selected=(d == selected),
            excluded_by_adverse=(d in adverse),
            reasons=reasons[d],
        ))

    non_selected = [d for d in eligible if d != selected]
    notes = [
        "第二阶段只做相对主线选择，不把未选中方向伪装成不利排除。",
        f"相对分差={margin:.3f}，选择置信度={confidence}。",
    ]
    if not adverse:
        notes.append("没有明确不利排除：该结果只能作为相对结构选择，置信度上限锁定为中。")
    if confidence == "低":
        notes.append("分差偏小：输出单一结构方向，但必须标记为低置信度相对选择。")
    if blocked_by_opening_lure:
        notes.append(
            "初赔一致性约束："
            + "、".join(sorted(blocked_by_opening_lure))
            + " 存在双公司利诱/过热候选且没有后续反转确认，不参与本轮最终结构方向选择。"
        )

    return RelativeSelectionResult(
        selected_direction=selected,
        confidence=confidence,
        method="v1.0.2_relative_structure_selection_after_integrated_judgement",
        adverse_exclusions=adverse,
        relative_non_selected=non_selected,
        scores=result_scores,
        notes=notes,
        score_margin=round(margin, 3),
        decision_eligible=bool(selected and adverse and margin >= 1.0),
    )
