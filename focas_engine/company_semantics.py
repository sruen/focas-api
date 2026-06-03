from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import (
    CompanyRelationResult,
    CompanySemanticReading,
    MotiveReading,
    OddsMove,
    P1CoreResult,
)
from .p1_core import profile_by_direction

DIRECTIONS = ("主胜", "平局", "客胜")
COMPANY_ALIASES = {
    "William": "威廉",
    "威廉": "威廉",
    "Ladbrokes": "立博",
    "Lad": "立博",
    "立博": "立博",
    "Avg": "市场平均",
    "Average": "市场平均",
    "市场平均": "市场平均",
}

# v0.9.1: do not collapse every non-adverse signal into “confirmation”.
MAINLINE_MOTIVE_KEYS = ("主线承接", "强承接", "真实保护")
RISK_REPAIR_MOTIVE_KEYS = ("保护", "风险修正", "风险修复", "降低赔付", "赔付修正")
DISPERSE_MOTIVE_KEYS = ("分流", "拉低营造", "过渡", "营造", "制造洼地")
ADVERSE_MOTIVE_KEYS = ("高阻", "缺承载", "不利压力", "打击信心")


def _cn_company(name: str) -> str:
    return COMPANY_ALIASES.get(name, name)


def _moves_by_company(moves: Iterable[OddsMove]) -> dict[str, list[OddsMove]]:
    grouped: dict[str, list[OddsMove]] = defaultdict(list)
    for m in moves:
        grouped[_cn_company(m.company)].append(m)
    return grouped


def _motives_by_company(motives: Iterable[MotiveReading]) -> dict[str, list[MotiveReading]]:
    grouped: dict[str, list[MotiveReading]] = defaultdict(list)
    for r in motives:
        grouped[_cn_company(r.company)].append(r)
    return grouped


def _action_by_direction(company_moves: list[OddsMove]) -> dict[str, str]:
    return {m.direction: m.action for m in company_moves}


def _largest_abs_delta(company_moves: list[OddsMove], directions: tuple[str, ...] = DIRECTIONS) -> str:
    options = [m for m in company_moves if m.direction in directions]
    if not options:
        return "未确认"
    return max(options, key=lambda m: abs(m.delta)).direction


def _coordinate_summary(company: str, odds_coordinates) -> str:
    if not odds_coordinates:
        return "缺少 Stage 8 坐标结果，公司语义只能降级。"
    for company_set in getattr(odds_coordinates, "company_sets", []):
        if _cn_company(company_set.company) != company:
            continue
        low = company_set.current_low_coordinate()
        if low is None:
            return "当前低赔方向未确认。"
        status = "表内确认" if low.lookup_status == "TABLE_READ_CONFIRMED" else low.lookup_status
        return (
            f"当前低赔={low.direction}，表方向={low.table_direction}，"
            f"体系={low.system}，区间={low.interval_id}，水位={low.water_band}，{status}。"
        )
    return "该公司未找到 Stage 8 坐标集合。"


def _p1_connection(direction: str, p1_core: P1CoreResult | None) -> str:
    profiles = profile_by_direction(p1_core)
    p = profiles.get(direction)
    if not p:
        return "P1 未给出该方向画像。"
    return (
        f"P1画像：信心承载={p.confidence_carrying}，分散支持={p.dispersion_support}，"
        f"预期开法={p.expected_board_style}，分布角色={p.distribution_role}。"
    )


def _can_upgrade_to_mainline(r: MotiveReading, p1_core: P1CoreResult | None) -> bool:
    """Return True only for signals that can count as mainline confirmation.

    v0.9.1 rule: risk repair/protection alone is not a mainline confirmation.
    It may be a repair of exposure, a dispersion tool, or a pure payout cut.
    """
    text = f"{r.motive_type} {r.bookmaker_meaning}"
    # 稳定只表示结构延续，不是主线确认；否则三项稳定都会被误计为承接。
    if "维持承接" in text or r.action == "稳定":
        return False
    if any(k in text for k in MAINLINE_MOTIVE_KEYS):
        return True
    # “保护” may upgrade only when P1 says the direction can carry confidence
    # and the motive wording does not merely say risk repair.
    if "保护" in text and "风险修正" not in text:
        profiles = profile_by_direction(p1_core)
        p = profiles.get(r.direction)
        return bool(p and p.confidence_carrying in {"足", "中高"} and p.distribution_role in {"原始承接项", "合力主项"})
    return False


def _motive_buckets(
    company_motives: list[MotiveReading],
    p1_core: P1CoreResult | None,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    mainline: list[str] = []
    risk_repair: list[str] = []
    disperses: list[str] = []
    adverses: list[str] = []
    evidence: list[str] = []
    for r in company_motives:
        text = f"{r.motive_type} {r.bookmaker_meaning}"
        if r.adverse_evidence or any(k in text for k in ADVERSE_MOTIVE_KEYS):
            adverses.append(r.direction)
            evidence.append(f"{r.direction}：{r.motive_type}，形成不利压力证据。")
            continue
        if "顶高承接边界" in text or "未打掉信心" in text:
            evidence.append(f"{r.direction}：{r.motive_type}，只表示抬高动作尚未直接打掉该方向，不计为机构给信心或主线确认。")
            continue
        if any(k in text for k in DISPERSE_MOTIVE_KEYS):
            disperses.append(r.direction)
            evidence.append(f"{r.direction}：{r.motive_type}，更像分流/过渡工具，不能计为主线确认。")
            continue
        if any(k in text for k in RISK_REPAIR_MOTIVE_KEYS):
            if _can_upgrade_to_mainline(r, p1_core):
                mainline.append(r.direction)
                evidence.append(f"{r.direction}：{r.motive_type}，在 P1 承载支持下可作为主线承接备选。")
            else:
                risk_repair.append(r.direction)
                evidence.append(f"{r.direction}：{r.motive_type}，仅为风险修正/赔付修正备选，不升级为主线确认。")
            continue
        if _can_upgrade_to_mainline(r, p1_core):
            mainline.append(r.direction)
            evidence.append(f"{r.direction}：{r.motive_type}，可作为主线承接备选。")
    return sorted(set(mainline)), sorted(set(risk_repair)), sorted(set(disperses)), sorted(set(adverses)), evidence


def _focus_william(company_moves: list[OddsMove]) -> tuple[str, list[str]]:
    actions = _action_by_direction(company_moves)
    evidence: list[str] = []
    draw_action = actions.get("平局", "未确认")
    if draw_action != "稳定":
        evidence.append(f"威廉平赔动作={draw_action}，优先纳入平赔语义。")
        return "平赔手法", evidence
    focus = _largest_abs_delta(company_moves, ("主胜", "客胜"))
    evidence.append("威廉平赔稳定，转为观察胜负两端是否承担分流或阻力。")
    if focus != "未确认":
        evidence.append(f"胜负两端最大动作方向={focus}。")
    return "平赔稳定 + 胜负辅助", evidence


def _focus_ladbrokes(company_moves: list[OddsMove]) -> tuple[str, list[str]]:
    focus = _largest_abs_delta(company_moves, ("主胜", "客胜"))
    evidence: list[str] = []
    if focus != "未确认":
        evidence.append(f"立博胜负两端最大动作方向={focus}，优先纳入胜负赔语义。")
        return "胜负赔手法", evidence
    evidence.append("立博胜负两端未形成显著动作，转为观察平赔是否配合。")
    return "胜负稳定 + 平赔辅助", evidence


def _focus_avg(company_moves: list[OddsMove]) -> tuple[str, list[str]]:
    focus = _largest_abs_delta(company_moves)
    if focus == "未确认":
        return "市场背景", ["市场平均缺少有效动作，只能作为背景，不参与公司确认。"]
    return "市场背景", [f"市场平均最大动作方向={focus}，仅作为市场背景，不替代威廉/立博。"]


def _semantic_role(company: str, mainline: list[str], risk: list[str], dispersed: list[str], adverses: list[str]) -> str:
    if company == "市场平均":
        return "市场背景"
    if adverses and not (mainline or risk):
        return "不利压力"
    roles = []
    if mainline:
        roles.append("主线承接备选")
    if risk:
        roles.append("风险修正备选")
    if dispersed:
        roles.append("分流/过渡备选")
    return " + ".join(roles) if roles else "确认不足"


def _confirmation_level(company: str, mainline: list[str], risk: list[str], adverses: list[str], warnings: list[str]) -> str:
    if company == "市场平均":
        return "背景参考"
    if adverses and not (mainline or risk):
        return "不利证据"
    if mainline:
        return "单公司主线承接备选"
    if risk:
        return "单公司风险修正备选"
    warnings.append("该公司未形成可用于方向确认的语义，只能标记确认不足。")
    return "确认不足"


def _build_company_reading(
    *,
    company: str,
    moves: list[OddsMove],
    motives: list[MotiveReading],
    p1_core: P1CoreResult | None,
    odds_coordinates,
) -> CompanySemanticReading:
    if company == "威廉":
        focus, focus_evidence = _focus_william(moves)
    elif company == "立博":
        focus, focus_evidence = _focus_ladbrokes(moves)
    else:
        focus, focus_evidence = _focus_avg(moves)

    mainline, risk, dispersed, adverses, motive_evidence = _motive_buckets(motives, p1_core)
    warnings: list[str] = []
    role = _semantic_role(company, mainline, risk, dispersed, adverses)
    confirmation = _confirmation_level(company, mainline, risk, adverses, warnings)
    main_direction = mainline[0] if mainline else risk[0] if risk else adverses[0] if adverses else dispersed[0] if dispersed else "未确认"

    reading = CompanySemanticReading(
        company=company,
        primary_focus=focus,
        semantic_role=role,
        supported_directions=mainline,
        mainline_confirmed_directions=mainline,
        risk_repair_directions=risk,
        dispersed_directions=dispersed,
        adverse_pressure_directions=adverses,
        confirmation_level=confirmation,
        p1_connection=_p1_connection(main_direction, p1_core) if main_direction != "未确认" else "未形成方向级 P1 挂接。",
        coordinate_connection=_coordinate_summary(company, odds_coordinates),
        evidence=focus_evidence + motive_evidence,
        warnings=warnings,
    )
    if company == "市场平均":
        reading.warnings.append("Avg 只能作为市场背景，不允许替代 William / Ladbrokes 公司语义。")
    return reading


def _combine_relation(readings: list[CompanySemanticReading]) -> CompanyRelationResult:
    hard = [r for r in readings if r.company in {"威廉", "立博"}]
    mainline_counts: dict[str, int] = defaultdict(int)
    risk_counts: dict[str, int] = defaultdict(int)
    dispersion_counts: dict[str, int] = defaultdict(int)
    adverse_counts: dict[str, int] = defaultdict(int)

    for r in hard:
        for d in r.mainline_confirmed_directions:
            mainline_counts[d] += 1
        for d in r.risk_repair_directions:
            risk_counts[d] += 1
        for d in r.dispersed_directions:
            dispersion_counts[d] += 1
        for d in r.adverse_pressure_directions:
            adverse_counts[d] += 1

    confirmed = sorted([d for d, count in mainline_counts.items() if count >= 2])
    risk_repair = sorted([d for d, count in risk_counts.items() if count >= 2])
    dispersion = sorted([d for d, count in dispersion_counts.items() if count >= 2])
    adverse_pressure = sorted([d for d, count in adverse_counts.items() if count >= 2])
    conflict = sorted([d for d in DIRECTIONS if (mainline_counts.get(d, 0) or risk_counts.get(d, 0)) and adverse_counts.get(d, 0)])

    touched = set(mainline_counts) | set(risk_counts) | set(dispersion_counts) | set(adverse_counts)
    unconfirmed = sorted([d for d in touched if d not in confirmed and d not in adverse_pressure])

    notes: list[str] = []
    if confirmed:
        relation = "同向确认"
        notes.append(f"William / Ladbrokes 对 {', '.join(confirmed)} 形成双公司主线承接确认。")
    elif conflict:
        relation = "冲突"
        notes.append(f"同一方向同时出现承接/修正与不利压力：{', '.join(conflict)}，后续主线需降级处理。")
    elif adverse_pressure:
        relation = "同向确认"
        notes.append(f"William / Ladbrokes 对 {', '.join(adverse_pressure)} 形成双公司不利压力证据。")
    elif risk_repair:
        relation = "同向确认"
        notes.append(f"William / Ladbrokes 对 {', '.join(risk_repair)} 形成双公司风险修正；这不是主线确认。")
    elif dispersion:
        relation = "同向确认"
        notes.append(f"William / Ladbrokes 对 {', '.join(dispersion)} 形成双公司分流/过渡；不能作为主线确认。")
    elif any(r.mainline_confirmed_directions or r.risk_repair_directions for r in hard) and len({tuple(r.mainline_confirmed_directions + r.risk_repair_directions) for r in hard if (r.mainline_confirmed_directions or r.risk_repair_directions)}) > 1:
        relation = "分工"
        notes.append("William 与 Ladbrokes 分别作用于不同方向，属于交叉或分工，不能直接视为同向确认。")
    elif unconfirmed:
        relation = "未确认"
        notes.append(f"仅单公司或弱语义触及 {', '.join(unconfirmed)}，确认不足不能排除其他方向。")
    else:
        relation = "未确认"
        notes.append("两家公司未形成清晰同向、交叉或双公司不利压力。")

    if risk_repair:
        notes.append(f"风险修正方向：{', '.join(risk_repair)}；只能用于风险解释，不能升级为主线确认。")
    if dispersion:
        notes.append(f"分流/过渡方向：{', '.join(dispersion)}；只能用于分布解释，不能升级为主线确认。")

    return CompanyRelationResult(
        relation_type=relation,
        readings=readings,
        confirmed_directions=confirmed,
        mainline_confirmed_directions=confirmed,
        risk_repair_directions=risk_repair,
        dispersion_directions=dispersion,
        unconfirmed_directions=unconfirmed,
        conflict_directions=conflict,
        adverse_pressure_directions=adverse_pressure,
        notes=notes,
    )


def analyze_company_semantics(
    *,
    moves: list[OddsMove],
    motive_readings: list[MotiveReading],
    p1_core: P1CoreResult | None,
    odds_coordinates=None,
) -> CompanyRelationResult:
    """Executable P2/P3/P7 layer.

    v0.9.1 boundary: company semantics are split into mainline confirmation,
    risk repair, dispersion/transition, and adverse pressure. Risk repair is not
    allowed to masquerade as mainline confirmation.
    """
    moves_grouped = _moves_by_company(moves)
    motives_grouped = _motives_by_company(motive_readings)
    companies = []
    for c in ("威廉", "立博", "市场平均"):
        if c in moves_grouped or c in motives_grouped:
            companies.append(c)
    for c in sorted(set(moves_grouped) | set(motives_grouped)):
        if c not in companies:
            companies.append(c)

    readings = [
        _build_company_reading(
            company=company,
            moves=moves_grouped.get(company, []),
            motives=motives_grouped.get(company, []),
            p1_core=p1_core,
            odds_coordinates=odds_coordinates,
        )
        for company in companies
    ]
    return _combine_relation(readings)
