from __future__ import annotations

from collections import defaultdict

from .models import (
    DirectionJudgement,
    IntegratedStructureJudgement,
    NaturalPull,
    OddsFaceAndCompanyMotiveAnalysis,
    OriginalBookMode,
    OriginalDistribution,
    StrengthContext,
)
from .odds_system import normalize_company
from .original_distribution import pressure_by_direction

DIRECTIONS = ("主胜", "平局", "客胜")


def _pull_map(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {pull.direction: pull for pull in pulls}


def _coordinate_evidence(direction: str, odds_coordinates) -> list[str]:
    if not odds_coordinates:
        return ["现代骨架坐标未生成。"]
    evidence = []
    for company_set in odds_coordinates.company_sets:
        if normalize_company(company_set.company) not in {"William", "Ladbrokes"}:
            continue
        coords = [
            coord
            for coord in company_set.coordinates
            if coord.time_point == "current" and coord.direction == direction
        ]
        if not coords:
            continue
        coord = coords[0]
        attr = "当前低赔项" if coord.is_snapshot_low else "非低赔反事实参考"
        evidence.append(
            f"{company_set.company}：{attr}已完成统一体系后的骨架比对，现实落点={coord.deviation}。"
        )
    return evidence or ["未找到该方向的现代骨架坐标。"]


def _motive_evidence(direction: str, stage_9: OddsFaceAndCompanyMotiveAnalysis) -> list[str]:
    evidence = []
    for reading in stage_9.action_motive_chain:
        if reading.direction != direction or normalize_company(reading.company) not in {"William", "Ladbrokes"}:
            continue
        evidence.append(f"{reading.company}：{reading.action} -> {reading.motive_type}")
    return evidence or ["William / Ladbrokes 未形成该方向动作动机。"]


def _opening_evidence(direction: str, stage_9: OddsFaceAndCompanyMotiveAnalysis) -> list[str]:
    evidence = []
    for reading in getattr(stage_9, "opening_motive_chain", []) or []:
        if reading.direction != direction or normalize_company(reading.company) not in {"William", "Ladbrokes"}:
            continue
        evidence.append(
            f"{reading.company}：初赔目的 -> {reading.motive_type}；"
            f"是否利用基本面或主客场拉力={'是' if reading.uses_fundamental_pull else '未形成明确证据'}；"
            f"后续约束={reading.selection_constraint}"
        )
    return evidence or ["William / Ladbrokes 未形成该方向初赔目的记录。"]


def _has_unresolved_opening_lure(
    direction: str,
    stage_9: OddsFaceAndCompanyMotiveAnalysis,
    confirmed: set[str],
) -> bool:
    if direction in confirmed:
        return False
    count = sum(
        1
        for reading in getattr(stage_9, "opening_motive_chain", []) or []
        if reading.direction == direction
        and normalize_company(reading.company) in {"William", "Ladbrokes"}
        and reading.selection_constraint == "REQUIRE_REVERSAL_CONFIRMATION"
    )
    return count >= 2


def _interval_adverse_counts(interval_audit) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if not interval_audit or not getattr(interval_audit, "ok", False):
        return counts
    for audit in getattr(interval_audit, "audits", []) or []:
        tags = set(getattr(audit, "semantic_tags", []) or [])
        if "抬胜" in tags:
            counts["主胜"] += 1
        if "抬负" in tags:
            counts["客胜"] += 1
    return counts


def integrated_structure_judgement(
    *,
    strength: StrengthContext,
    pulls: list[NaturalPull],
    original_distribution: OriginalDistribution,
    book_mode: OriginalBookMode,
    odds_coordinates,
    interval_audit,
    stage_9: OddsFaceAndCompanyMotiveAnalysis,
) -> IntegratedStructureJudgement:
    """Stage 10: synthesize the complete chain instead of printing a status table."""
    pressures = pressure_by_direction(original_distribution)
    pull_map = _pull_map(pulls)
    relation = stage_9.company_relation
    hard_adverse_counts: dict[str, int] = defaultdict(int)
    risk_repair = set(getattr(relation, "risk_repair_directions", []) or [])
    relation_adverse = set(getattr(relation, "adverse_pressure_directions", []) or [])
    confirmed = set(getattr(relation, "confirmed_directions", []) or [])
    interval_adverse = _interval_adverse_counts(interval_audit)
    expected_interval = getattr(getattr(interval_audit, "expected", None), "expected_interval", None)
    expected_interval_source = getattr(getattr(interval_audit, "expected", None), "expected_interval_source", None)

    for reading in stage_9.action_motive_chain:
        if normalize_company(reading.company) in {"William", "Ladbrokes"} and reading.adverse_evidence:
            hard_adverse_counts[reading.direction] += 1

    adverse = []
    qualified = []
    unconfirmed = []
    relative_weaker = []
    summary = []
    text_by_direction: dict[str, str] = {}

    for direction in DIRECTIONS:
        pull = pull_map.get(direction)
        pressure = pressures.get(direction, "未确认")
        evidence = [
            f"广义实力：主队={strength.home_grade or '未确认'}，客队={strength.away_grade or '未确认'}，"
            f"动态差={strength.final_gap or '未确认'}，P4理论区间={expected_interval or '未确认'}，"
            f"来源={expected_interval_source or '未确认'}。",
            f"自然拉力：{pull.strength if pull else '未确认'}；原始压力：{pressure}；"
            f"市场第一眼={original_distribution.first_eye_direction or '未确认'}。",
            f"原书模式：{book_mode.mode or '未确认'}。",
            f"赔率组合赔面：{stage_9.odds_face_shape}。",
            *_opening_evidence(direction, stage_9),
            *_coordinate_evidence(direction, odds_coordinates),
            *_motive_evidence(direction, stage_9),
        ]
        unresolved_opening_lure = _has_unresolved_opening_lure(direction, stage_9, confirmed)
        is_adverse = (
            hard_adverse_counts[direction] >= 2
            or direction in relation_adverse
            or interval_adverse[direction] >= 2
        )
        if is_adverse:
            adverse.append(direction)
            conclusion = (
                "形成明确不利处理：至少两家公司或理论区间审计给出同向完整证据链。"
                "该排除不是由单次抬高、拉低或原始压力弱机械推出。"
            )
            status = "不利"
        else:
            table_confirmed_count = 0
            if odds_coordinates:
                for company_set in odds_coordinates.company_sets:
                    if normalize_company(company_set.company) not in {"William", "Ladbrokes"}:
                        continue
                    current_low = company_set.current_low_coordinate()
                    if (
                        current_low
                        and current_low.direction == direction
                        and current_low.lookup_status == "TABLE_READ_CONFIRMED"
                    ):
                        table_confirmed_count += 1
            is_qualified = (
                not unresolved_opening_lure
                and (
                    direction in confirmed
                    or (pressure == "强" and direction in risk_repair and table_confirmed_count >= 1)
                )
            )
            if is_qualified:
                qualified.append(direction)
                conclusion = (
                    "未形成不利排除，并具备结构主线资格。"
                    "资格来自原始承载、按机构体系查表后的原始赔率落点与公司目的共同支持，不是动作本身确认。"
                )
                status = "中性"
            else:
                unconfirmed.append(direction)
                conclusion = "当前没有完整不利证据链，但支持链也不足，只能标记未确认，不能排除。"
                if unresolved_opening_lure:
                    conclusion += " 双公司初赔存在利用基本面或主客场拉力的利诱/过热候选，且后续没有反转确认；不得在第二阶段仅凭基本面重新选回。"
                status = "未确认"
                if pressure == "弱":
                    relative_weaker.append(direction)
        evidence.append(conclusion)
        text_by_direction[direction] = " ".join(evidence)
        summary.append(DirectionJudgement(direction=direction, status=status, reasons=evidence))

    reasoning = [
        "综合结构判断负责合盘：基本面、广义实力、自然拉力、原始分布、原书模式、机构返还率体系对应骨架区间和公司目的必须共同进入判断。",
        f"明确不利排除={adverse or ['无']}；未确认={unconfirmed or ['无']}；具备主线资格={qualified or ['无']}。",
        "未确认不能排除；相对弱也不等于不利排除。",
    ]
    return IntegratedStructureJudgement(
        home_integrated_judgement=text_by_direction["主胜"],
        draw_integrated_judgement=text_by_direction["平局"],
        away_integrated_judgement=text_by_direction["客胜"],
        adverse_excluded_directions=adverse,
        unconfirmed_directions=unconfirmed,
        relative_weaker_directions=relative_weaker,
        mainline_qualified_directions=qualified,
        summary_status=summary,
        reasoning=reasoning,
    )
