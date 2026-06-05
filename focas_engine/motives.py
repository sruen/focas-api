from __future__ import annotations

from .models import (
    CompanyOdds,
    MotiveReading,
    NaturalPull,
    OddsMove,
    OddsSystemConversion,
    OpeningMotiveReading,
    OriginalDistribution,
    P1CoreResult,
    TableLookupResult,
)
from .odds_system import conversion_map, normalize_company
from .original_distribution import pressure_by_direction
from .p1_core import profile_by_direction

DIRECTION_MAP = {
    "主胜": ("home", "主胜"),
    "平局": ("draw", "平局"),
    "客胜": ("away", "客胜"),
}
LOW_SIDE_TO_DIRECTION = {"主低赔": "主胜", "客低赔": "客胜", "平低赔_特殊": "平局"}


def odds_moves(
    odds: list[CompanyOdds],
    *,
    conversions: list[OddsSystemConversion] | None = None,
    tolerance: float = 0.005,
) -> list[OddsMove]:
    """Build actions from institution-published odds.

    Return-rate systems only route table lookup. They never rewrite the odds
    values used to describe opening-to-current movement.
    """
    moves: list[OddsMove] = []
    by_conversion = conversion_map(conversions or [])
    for company_odds in odds:
        company = normalize_company(company_odds.company)
        initial_conversion = by_conversion.get((company, "initial"))
        current_conversion = by_conversion.get((company, "current"))
        if initial_conversion and current_conversion:
            initial_snapshot = initial_conversion.comparison_snapshot()
            current_snapshot = current_conversion.comparison_snapshot()
            basis = "raw_institution_odds"
        else:
            initial_snapshot = company_odds.initial
            current_snapshot = company_odds.current
            basis = "raw_odds_legacy_only"
        for attr, direction in (("home", "主胜"), ("draw", "平局"), ("away", "客胜")):
            initial = float(getattr(initial_snapshot, attr))
            current = float(getattr(current_snapshot, attr))
            delta = round(current - initial, 4)
            if delta > tolerance:
                action = "抬高"
            elif delta < -tolerance:
                action = "拉低"
            else:
                action = "稳定"
            moves.append(OddsMove(company_odds.company, direction, initial, current, delta, action, basis))
    return moves


def _pull_by_direction(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {pull.direction: pull for pull in pulls}


def opening_motive_readings(
    *,
    interval_audit,
    original_distribution: OriginalDistribution | None,
    pulls: list[NaturalPull],
    context_summary: str = "",
) -> list[OpeningMotiveReading]:
    """Explain the opening low-odds position before interpreting later moves.

    The opening board must be compared with the pre-odds distribution and the
    P4 bridge interval. Otherwise later relative scoring can accidentally turn
    a fundamentals-driven lure interpretation back into a structural direction.
    """
    if not interval_audit:
        return []
    pressures = pressure_by_direction(original_distribution)
    pull_map = _pull_by_direction(pulls)
    first_eye = original_distribution.first_eye_direction if original_distribution else None
    readings: list[OpeningMotiveReading] = []
    for audit in getattr(interval_audit, "audits", []) or []:
        direction = getattr(audit, "opening_low_direction", None)
        if direction not in DIRECTION_MAP:
            continue
        pull = pull_map.get(direction)
        pull_strength = pull.strength if pull and pull.strength else "未确认"
        pressure = pressures.get(direction, "未确认")
        delta = getattr(audit, "interval_delta", None)
        skeleton_confirmed = getattr(audit, "hard_status", "UNCONFIRMED") == "CONFIRMED"
        uses_fundamental_pull = skeleton_confirmed and (
            direction == first_eye or (pull_strength == "强" and pressure == "强")
        )

        if not skeleton_confirmed:
            motive = "机构体系下的初赔骨架尚未确认，不得推断机构利用题材"
            constraint = "SKELETON_REVIEW_REQUIRED"
        elif delta is None:
            motive = "初赔区间无法比较，机构目的未确认"
            constraint = "UNCONFIRMED"
        elif delta > 0 and uses_fundamental_pull:
            motive = "利用基本面 / 主客场第一眼拉力压低初赔，利诱或过热风险候选"
            constraint = "REQUIRE_REVERSAL_CONFIRMATION"
        elif delta > 0 and pressure == "弱":
            motive = "低承载方向深开，拉低营造或利诱风险候选"
            constraint = "REQUIRE_REVERSAL_CONFIRMATION"
        elif delta > 0:
            motive = "现实初赔深于理论区间，承接或吸收风险待后续验证"
            constraint = "OBSERVE_LATER_ACTION"
        elif delta < 0 and uses_fundamental_pull:
            motive = "利用基本面 / 主客场第一眼拉力顶高观察，阻力或承接待后续验证"
            constraint = "OBSERVE_LATER_ACTION"
        elif delta < 0:
            motive = "现实初赔浅于理论区间，需观察是否为阻力或组合分流"
            constraint = "OBSERVE_LATER_ACTION"
        else:
            motive = "现实初赔顺理论区间，需结合三项赔面判断承接或吸收"
            constraint = "OBSERVE_LATER_ACTION"

        reasoning = [
            f"公司={audit.company}；初赔低赔方向={direction}；现实区间={audit.opening_interval_id}；"
            f"P4理论区间={audit.expected_interval_id}；区间差={delta}。",
            f"基本面自然拉力={pull_strength}；原始压力={pressure}；市场第一眼={first_eye or '未确认'}；"
            f"是否利用基本面或主客场拉力={'是' if uses_fundamental_pull else '未形成明确证据'}。",
            f"赛事语义修正={context_summary or '未提供'}。",
            f"初赔目的={motive}；后续约束={constraint}。",
        ]
        readings.append(OpeningMotiveReading(
            company=audit.company,
            direction=direction,
            opening_interval_id=audit.opening_interval_id,
            expected_interval_id=audit.expected_interval_id,
            interval_delta=delta,
            natural_pull=pull_strength,
            original_pressure=pressure,
            first_eye_direction=first_eye,
            uses_fundamental_pull=uses_fundamental_pull,
            motive_type=motive,
            selection_constraint=constraint,
            reasoning=reasoning,
        ))
    return readings


def _table_position(move: OddsMove, table_results: list[TableLookupResult]) -> str:
    if move.direction != "主胜":
        return "非低赔精确轴；仅作组合赔率参考"
    move_company = normalize_company(move.company)
    for result in table_results:
        if normalize_company(result.company) != move_company:
            continue
        if LOW_SIDE_TO_DIRECTION.get(result.direction) != move.direction:
            return "非当前低赔方向；仅作组合赔面解释"
        return result.deviation
    return "未查表"


def judge_odds_action_motive(
    *,
    odds_action: OddsMove,
    original_distribution: OriginalDistribution | None,
    natural_pull: NaturalPull | None,
    strength_gap: str | None,
    expected_interval,
    table_position: str,
    odds_face: str,
    company_context: str,
    p1_profile=None,
) -> MotiveReading:
    """Interpret one action only after contextual evidence has been assembled.

    Raising or lowering odds is never mapped directly to a directional verdict.
    """
    pressure = pressure_by_direction(original_distribution).get(odds_action.direction, "未确认")
    pull_strength = natural_pull.strength if natural_pull else None
    confidence = getattr(p1_profile, "confidence_carrying", "未确认")
    dispersion = getattr(p1_profile, "dispersion_support", "未确认")
    natural_pull_match = (
        "自然拉力与原始压力同向"
        if pull_strength == pressure
        else "自然拉力与原始压力需要交叉解释"
    )
    reasoning = [
        f"动作={odds_action.action}；比较口径={odds_action.comparison_basis}。",
        f"原始压力={pressure}；自然拉力={pull_strength or '未确认'}；信心承载={confidence}；分散支持={dispersion}。",
        f"理论档位差={strength_gap or '未确认'}；表内落点={table_position}；赔面={odds_face}；公司语境={company_context}。",
        f"五道门：信心承载={confidence}；分散有效性={dispersion}；基本面自然拉力={pull_strength or '未确认'}；"
        f"表内区间={table_position}；公司目的需结合三项组合判断。",
    ]
    target = odds_action.direction
    dispersion_target = None
    protected = None
    attacked = None
    adverse = False
    return_incentive = "未形成提高受注回报解释"

    if odds_action.action == "稳定":
        motive = "维持结构 / 动机待确认"
        meaning = "赔率稳定只说明当前结构延续，不能单独确认主线，也不能单独排除方向。"
    elif odds_action.action == "抬高":
        return_incentive = f"{target}回报被提高，是否具有受注意义仍需结合承载与分散判断"
        if pressure == "弱" and "高于表内上界" in table_position:
            motive = "打击信心 / 风险释放备选"
            attacked = target
            adverse = True
            meaning = (
                "该方向原始压力弱，且按机构体系查表后的原始低赔落点高于表内上界；抬高动作与缺乏承载共同形成不利证据。"
                "不利来自完整证据链，不来自抬高动作本身。"
            )
        elif pressure == "强" and confidence in {"足", "中高"}:
            motive = "顶高承接 / 提高回报备选"
            meaning = (
                "该方向具有原始承载，抬高可能是顶高承接、提高回报或风险释放。"
                "当前只能保留备选解释，不能写成给信心、确认主线或不利排除。"
            )
        else:
            motive = "降低信心 / 顶高过渡 / 风险释放待判断"
            meaning = "抬高动作存在多种目的，现有证据不足以确认其在打击、承接还是释放风险。"
    elif odds_action.action == "拉低":
        return_incentive = f"{target}回报被压低，不能机械写成保护、给信心或分流"
        if pressure == "强" and confidence in {"足", "中高"}:
            motive = "降低赔付 / 风险修复备选"
            protected = target
            meaning = (
                "该方向已有原始承载，拉低可能是降低赔付或风险修复。"
                "仍不能把拉低机械等同于保护或主线确认。"
            )
        elif pressure == "弱":
            motive = "制造洼地 / 分流受注备选"
            dispersion_target = target
            meaning = (
                "该方向原始信心弱，拉低可能在制造赔率洼地或承担分流。"
                "分流有效性仍需看三项赔面和双公司关系，不能反向确认其他方向。"
            )
        else:
            motive = "给信心 / 降低赔付 / 分流受注待判断"
            meaning = "拉低动作存在多种目的，必须结合原始分布、表内落点和公司分工继续判断。"
    else:
        motive = "动作未识别"
        meaning = "没有可解释的赔率动作，不能据此形成方向结论。"

    misread = f"不能把{odds_action.direction}{odds_action.action}直接写成方向确认、不利排除、保护或分流。"
    reasoning.append(meaning)
    return MotiveReading(
        company=odds_action.company,
        direction=odds_action.direction,
        action=odds_action.action,
        natural_pull=pull_strength,
        confidence_carrying=confidence,
        dispersion_effectiveness=dispersion,
        motive_type=motive,
        bookmaker_meaning=meaning,
        adverse_evidence=adverse,
        target_direction=target,
        dispersion_target=dispersion_target,
        protected_direction=protected,
        attacked_direction=attacked,
        misread_risk=misread,
        reasoning=reasoning,
        table_interval_position=table_position,
        company_purpose=motive,
        odds_move_semantics=meaning,
        adverse_status="不利" if adverse else "未确认",
        return_incentive=return_incentive,
        natural_pull_match=natural_pull_match,
    )


def motive_readings(
    *,
    moves: list[OddsMove],
    pulls: list[NaturalPull],
    table_results: list[TableLookupResult],
    p1_core: P1CoreResult | None = None,
    original_distribution: OriginalDistribution | None = None,
    strength_gap: str | None = None,
    expected_interval=None,
    odds_face: str = "中庸分布",
    context_summary: str = "",
) -> list[MotiveReading]:
    pmap = _pull_by_direction(pulls)
    profiles = profile_by_direction(p1_core)
    readings: list[MotiveReading] = []
    for move in moves:
        readings.append(
            judge_odds_action_motive(
                odds_action=move,
                original_distribution=original_distribution,
                natural_pull=pmap.get(move.direction),
                strength_gap=strength_gap,
                expected_interval=expected_interval,
                table_position=_table_position(move, table_results),
                odds_face=odds_face,
                company_context=f"{normalize_company(move.company)}；{context_summary}" if context_summary else normalize_company(move.company),
                p1_profile=profiles.get(move.direction),
            )
        )
    return readings
