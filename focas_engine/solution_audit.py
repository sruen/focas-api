from __future__ import annotations

from pathlib import Path
from statistics import mean

from .models import (
    BookmakerTopicUsageAudit,
    BookmakerTopicUsageDirection,
    DirectionPsychologicalInterval,
    ExpectedOpeningInterval,
    FinalStructureJudgement,
    FutureAdjustmentItem,
    FutureAdjustmentPlan,
    MarketPullAudit,
    MarketPullDirectionAudit,
    NarrativeAuditResult,
    NaturalPull,
    OpeningBoardAudit,
    OpeningBoardCompanyAudit,
    OpeningBoardDirectionAudit,
    OptimalScenario,
    OptimalSolutionAudit,
    OriginalDistribution,
    PsychologicalIntervalAudit,
    SkeletonIntervalProfile,
)
from .odds_system import normalize_company
from .original_distribution import pressure_by_direction
from .table_lookup import load_interval_profile

DIRECTIONS = ("主胜", "平局", "客胜")
HARD_COMPANIES = {"William", "Ladbrokes"}
ODDS_ATTR_BY_DIRECTION = {"主胜": "home", "平局": "draw", "客胜": "away"}
STRENGTH_SCORE = {
    "极强": 2.35,
    "强": 2.0,
    "中强": 1.6,
    "中": 1.0,
    "中弱": 0.7,
    "弱": 0.35,
    "未确认": 0.6,
    "UNCONFIRMED": 0.6,
    None: 0.6,
}


def _coord(company_set, time_point: str):
    return next((item for item in company_set.coordinates if item.time_point == time_point), None)


def _hard_company_sets(odds_coordinates) -> list:
    if not odds_coordinates:
        return []
    return [
        item
        for item in odds_coordinates.company_sets
        if normalize_company(item.company) in HARD_COMPANIES
    ]


def _profile_range(
    profile: SkeletonIntervalProfile | None,
    direction: str,
) -> tuple[float | None, float | None, str]:
    if profile is None:
        return None, None, "UNCONFIRMED"
    if direction == "主胜":
        return profile.main_price_min, profile.main_price_max, "PRECISE_MAIN_PRICE_AXIS"
    if direction == "平局":
        return profile.draw_reference_min, profile.draw_reference_max, "MARKET_LADDER_REFERENCE"
    return profile.away_reference_min, profile.away_reference_max, "MARKET_LADDER_REFERENCE"


def _range_deviation(value: float, lower: float | None, upper: float | None) -> float | None:
    if lower is None or upper is None:
        return None
    if value < lower:
        return round(value - lower, 6)
    if value > upper:
        return round(value - upper, 6)
    return 0.0


def _position_status(value: float, lower: float | None, upper: float | None) -> str:
    if lower is None or upper is None:
        return "RANGE_REVIEW_REQUIRED"
    if value < lower:
        return "LOWER_THAN_PSYCHOLOGICAL_INTERVAL"
    if value > upper:
        return "HIGHER_THAN_PSYCHOLOGICAL_INTERVAL"
    return "WITHIN_PSYCHOLOGICAL_INTERVAL"


def _direction_semantic(direction: str, status: str) -> str:
    if status == "RANGE_REVIEW_REQUIRED":
        return "表内三项心理区间不完整，只能保留观察，不能冒充精确判断。"
    if direction == "主胜":
        if status == "LOWER_THAN_PSYCHOLOGICAL_INTERVAL":
            return "主赔低于理论心理区间，可能是控赔、增信或深开，需要看平负是否能分散主胜。"
        if status == "HIGHER_THAN_PSYCHOLOGICAL_INTERVAL":
            return "主赔高于理论心理区间，可能是阻主、降热或韬开；不能直接判定主队不利。"
        return "主赔落在理论心理区间内，先按骨架合理位处理。"
    if direction == "平局":
        if status == "LOWER_THAN_PSYCHOLOGICAL_INTERVAL":
            return "平赔低于理论心理区间，平局承接增强，常用于分散主胜或客胜压力。"
        if status == "HIGHER_THAN_PSYCHOLOGICAL_INTERVAL":
            return "平赔高于理论心理区间，可能形成阻平，也可能说明平局分流不足。"
        return "平赔处于理论参考范围内，可作为中性分洪区观察。"
    if status == "LOWER_THAN_PSYCHOLOGICAL_INTERVAL":
        return "客胜低于理论心理区间，客队冷门或不败题材被增强。"
    if status == "HIGHER_THAN_PSYCHOLOGICAL_INTERVAL":
        return "客胜高于理论心理区间，可能阻客、压制客胜或放弃客胜分流。"
    return "客胜处于理论参考范围内，按常规冷门承接观察。"


def _pull_map(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {pull.direction: pull for pull in pulls}


def _narrative_items(narrative_audit: NarrativeAuditResult | None) -> dict[str, object]:
    if narrative_audit is None:
        return {}
    return {item.direction: item for item in narrative_audit.direction_audits}


def _topic_map(narrative_audit: NarrativeAuditResult | None) -> dict[str, list[str]]:
    return {
        direction: list(getattr(item, "available_topics", []))
        for direction, item in _narrative_items(narrative_audit).items()
    }


def _percent_label(percent: float) -> str:
    if percent >= 40:
        return "强"
    if percent >= 25:
        return "中"
    return "弱"


def _opening_items(opening_board_audit: OpeningBoardAudit | None, direction: str) -> list[OpeningBoardDirectionAudit]:
    if opening_board_audit is None:
        return []
    return [
        item
        for company in opening_board_audit.company_audits
        for item in company.direction_audits
        if item.direction == direction
    ]


def _action_counts(items: list[OpeningBoardDirectionAudit]) -> dict[str, int]:
    counts = {"拉低": 0, "抬高": 0, "稳定": 0}
    for item in items:
        counts[item.action] = counts.get(item.action, 0) + 1
    return counts


def _dominant_action(items: list[OpeningBoardDirectionAudit]) -> str:
    if not items:
        return "未确认"
    counts = _action_counts(items)
    return max(counts, key=lambda key: counts[key])


def _avg_opening_fit(items: list[OpeningBoardDirectionAudit]) -> float:
    if not items:
        return 0.0
    score_by_status = {
        "WITHIN_PSYCHOLOGICAL_INTERVAL": 0.72,
        "LOWER_THAN_PSYCHOLOGICAL_INTERVAL": 0.66,
        "HIGHER_THAN_PSYCHOLOGICAL_INTERVAL": 0.40,
        "RANGE_REVIEW_REQUIRED": 0.25,
    }
    return mean(score_by_status.get(item.position_status, 0.25) for item in items)


def _movement_support_score(items: list[OpeningBoardDirectionAudit], *, target: bool) -> float:
    if not items:
        return 0.0
    action = _dominant_action(items)
    if target:
        if action == "拉低":
            return 0.78
        if action == "稳定":
            return 0.66
        return 0.50
    if action == "拉低":
        return 0.72
    if action == "稳定":
        return 0.52
    return 0.36


def _market_pull_item(market_pull_audit: MarketPullAudit | None, direction: str) -> MarketPullDirectionAudit | None:
    if market_pull_audit is None:
        return None
    return next((item for item in market_pull_audit.directions if item.direction == direction), None)


def _usage_item(
    usage_audit: BookmakerTopicUsageAudit | None,
    direction: str,
) -> BookmakerTopicUsageDirection | None:
    if usage_audit is None:
        return None
    return next((item for item in usage_audit.direction_usages if item.direction == direction), None)


def _range_label(item: OpeningBoardDirectionAudit | None) -> str:
    if item is None:
        return "未确认"
    return f"{item.interval_id}区/{item.water_band or '水位未确认'}/{item.precision}"


def build_psychological_interval_audit(
    *,
    expected: ExpectedOpeningInterval | None,
    odds_coordinates,
    xlsx_path: str | Path,
) -> PsychologicalIntervalAudit:
    if expected is None or expected.expected_interval_id is None:
        return PsychologicalIntervalAudit(
            expected_interval_id=None,
            expected_water_band=None,
            expected_low_side="未确认",
            notes=["未确认理论区间，无法生成三项心理区间审计。"],
        )

    direction_intervals: list[DirectionPsychologicalInterval] = []
    systems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for company_set in _hard_company_sets(odds_coordinates):
        initial = _coord(company_set, "initial")
        if initial is None:
            continue
        system = initial.system
        if system not in systems:
            systems.append(system)
        profile = load_interval_profile(str(xlsx_path), system, int(expected.expected_interval_id))
        for direction in DIRECTIONS:
            key = (system, direction)
            if key in seen:
                continue
            seen.add(key)
            lower, upper, precision = _profile_range(profile, direction)
            notes = []
            if precision != "PRECISE_MAIN_PRICE_AXIS":
                notes.append("该项来自骨架表机构档口参考，不得冒充主赔精确轴。")
            direction_intervals.append(
                DirectionPsychologicalInterval(
                    direction=direction,
                    system=system,
                    interval_id=expected.expected_interval_id,
                    expected_water_band=expected.expected_water_band,
                    odds_min=lower,
                    odds_max=upper,
                    precision=precision,
                    profile_status=profile.status,
                    notes=notes,
                )
            )

    return PsychologicalIntervalAudit(
        expected_interval_id=expected.expected_interval_id,
        expected_water_band=expected.expected_water_band,
        expected_low_side=expected.expected_low_side,
        systems=systems,
        direction_intervals=direction_intervals,
        notes=[
            "三项区间按机构初赔返还率识别出的 89-96 体系 sheet 读取；赔率不做数值转换。",
            "主胜为当前骨架精确轴；平局和客胜若表内只提供参考范围，报告必须保持参考口径。",
        ],
    )


def build_opening_board_audit(
    *,
    expected: ExpectedOpeningInterval | None,
    odds_coordinates,
    xlsx_path: str | Path,
) -> OpeningBoardAudit:
    audit = OpeningBoardAudit()
    if expected is None or expected.expected_interval_id is None:
        audit.notes.append("未确认理论区间，不能完成三项初赔对照。")
        return audit

    for company_set in _hard_company_sets(odds_coordinates):
        initial = _coord(company_set, "initial")
        current = _coord(company_set, "current")
        if initial is None or current is None:
            audit.notes.append(f"{company_set.company} 缺少初赔或最新赔率坐标。")
            continue
        profile = load_interval_profile(str(xlsx_path), initial.system, int(expected.expected_interval_id))
        company_audit = OpeningBoardCompanyAudit(
            company=company_set.company,
            system=initial.system,
            return_rate=initial.return_rate,
        )
        for direction in DIRECTIONS:
            attr = ODDS_ATTR_BY_DIRECTION[direction]
            opening = float(getattr(initial, f"odds_{attr}"))
            latest = float(getattr(current, f"odds_{attr}"))
            lower, upper, precision = _profile_range(profile, direction)
            status = _position_status(opening, lower, upper)
            delta = latest - opening
            action = "抬高" if delta > 0.005 else "拉低" if delta < -0.005 else "稳定"
            company_audit.direction_audits.append(
                OpeningBoardDirectionAudit(
                    company=company_set.company,
                    system=initial.system,
                    direction=direction,
                    opening_odds=opening,
                    current_odds=latest,
                    action=action,
                    expected_min=lower,
                    expected_max=upper,
                    range_deviation=_range_deviation(opening, lower, upper),
                    position_status=status,
                    semantic=_direction_semantic(direction, status),
                    precision=precision,
                    interval_id=expected.expected_interval_id,
                    water_band=expected.expected_water_band,
                )
            )
        audit.company_audits.append(company_audit)

    audit.ok = bool(audit.company_audits) and all(
        item.position_status != "RANGE_REVIEW_REQUIRED"
        for company in audit.company_audits
        for item in company.direction_audits
    )
    audit.notes.extend([
        "三项初赔对照使用机构发布的原始赔率。",
        "低于区间或高于区间只是赔率功能信号，必须结合原始拉力与题材分散能力解释。",
    ])
    return audit


def build_market_pull_audit(
    *,
    pulls: list[NaturalPull],
    original_distribution: OriginalDistribution | None,
    narrative_audit: NarrativeAuditResult | None,
) -> MarketPullAudit:
    pmap = _pull_map(pulls)
    topics = _topic_map(narrative_audit)
    pressures = pressure_by_direction(original_distribution)
    raw_scores: dict[str, float] = {}

    for direction in DIRECTIONS:
        pull = pmap.get(direction)
        score = STRENGTH_SCORE.get(pull.strength if pull else None, 0.6)
        pressure = pressures.get(direction)
        if pressure == "强":
            score += 0.65
        elif pressure == "中":
            score += 0.25
        if pull and pull.easy_to_receive:
            score += 0.25
        if pull and pull.first_eye_direction:
            score += 0.20
        if topics.get(direction):
            score += min(len(topics[direction]), 3) * 0.08
        raw_scores[direction] = max(score, 0.05)

    total = sum(raw_scores.values()) or 1.0
    audit = MarketPullAudit(
        distribution_type=original_distribution.distribution_type if original_distribution else "UNCONFIRMED",
        notes=[
            "百分比表示市场心理拉力占比，不是赛果概率。",
            "拉力由基本面题材、广义实力压力、原始分布和市场可见度共同计算。",
        ],
    )
    for direction in DIRECTIONS:
        pull = pmap.get(direction)
        percent = raw_scores[direction] / total * 100
        source_topics = topics.get(direction) or ([pull.facts] if pull and pull.facts else [])
        dispersion = bool(
            original_distribution
            and original_distribution.dispersion_available.get(direction)
        )
        audit.directions.append(
            MarketPullDirectionAudit(
                direction=direction,
                pull_strength=pull.strength if pull and pull.strength else "未确认",
                pull_score=round(raw_scores[direction], 4),
                pull_percent=round(percent, 4),
                pull_label=_percent_label(percent),
                topic_sources=[item for item in source_topics if item],
                dispersion_available=dispersion,
                first_eye_direction=bool(
                    (pull.first_eye_direction if pull else False)
                    or (original_distribution and original_distribution.first_eye_direction == direction)
                ),
            )
        )
    return audit


def build_bookmaker_topic_usage_audit(
    *,
    market_pull_audit: MarketPullAudit | None,
    narrative_audit: NarrativeAuditResult | None,
    opening_board_audit: OpeningBoardAudit | None,
) -> BookmakerTopicUsageAudit:
    topics = _topic_map(narrative_audit)
    nitems = _narrative_items(narrative_audit)
    audit = BookmakerTopicUsageAudit(notes=[
        "有题材不等于机构使用；必须由初赔落点或变赔动作证明。",
        "使用方式按吸收、分流、阻挡、诱导、压制、放弃归类。",
    ])

    for direction in DIRECTIONS:
        pull = _market_pull_item(market_pull_audit, direction)
        items = _opening_items(opening_board_audit, direction)
        narrative_item = nitems.get(direction)
        used_evidence: list[str] = []
        usage_modes: list[str] = []

        if narrative_item and getattr(narrative_item, "institution_use_status", None) == "USED":
            used_evidence.extend(getattr(narrative_item, "institution_use_evidence", []))
            usage_modes.append("题材明示使用")
        for item in items:
            if item.position_status == "LOWER_THAN_PSYCHOLOGICAL_INTERVAL":
                used_evidence.append(f"{item.company} 初赔低于{direction}心理区间")
                usage_modes.append("吸收/增信" if direction != "平局" else "分流/承接")
            elif item.position_status == "HIGHER_THAN_PSYCHOLOGICAL_INTERVAL":
                used_evidence.append(f"{item.company} 初赔高于{direction}心理区间")
                usage_modes.append("阻挡/压制")
            if item.action == "拉低":
                used_evidence.append(f"{item.company} 后续拉低{direction}")
                usage_modes.append("吸收/分流")
            elif item.action == "抬高":
                used_evidence.append(f"{item.company} 后续抬高{direction}")
                usage_modes.append("阻挡/降热")

        available_topics = topics.get(direction, [])
        institution_used = bool(used_evidence)
        unused_topics = [] if institution_used else available_topics
        audit.direction_usages.append(
            BookmakerTopicUsageDirection(
                direction=direction,
                available_topics=available_topics,
                original_pull_percent=pull.pull_percent if pull else None,
                original_pull_label=pull.pull_label if pull else "UNCONFIRMED",
                institution_use_status="USED" if institution_used else "NOT_USED",
                usage_mode="；".join(dict.fromkeys(usage_modes)) if usage_modes else "未使用",
                used_evidence=list(dict.fromkeys(used_evidence)),
                unused_topics=unused_topics,
                unused_reason=(
                    None
                    if institution_used
                    else "有题材但初赔落点和后续变赔未形成使用证据。"
                    if available_topics
                    else "该方向缺少可见题材，无法作为主要分散项。"
                ),
            )
        )
    return audit


def _scenario_expected_plan(
    target_direction: str,
    expected: ExpectedOpeningInterval | None,
    opening_board_audit: OpeningBoardAudit | None,
) -> dict[str, str]:
    plan: dict[str, str] = {}
    for direction in DIRECTIONS:
        item = next(iter(_opening_items(opening_board_audit, direction)), None)
        base = _range_label(item)
        if direction == target_direction:
            plan[direction] = f"{base}，目标项应处于可承载位，不宜脱离心理区间"
        else:
            plan[direction] = f"{base}，协助分流项应保留市场可接受度"
    if not plan and expected:
        for direction in DIRECTIONS:
            plan[direction] = f"{expected.expected_interval_id}区/{expected.expected_water_band or '水位未确认'}"
    return plan


def _score_scenario(
    target_direction: str,
    *,
    expected: ExpectedOpeningInterval | None,
    market_pull_audit: MarketPullAudit | None,
    opening_board_audit: OpeningBoardAudit | None,
    usage_audit: BookmakerTopicUsageAudit | None,
) -> OptimalScenario:
    supports = [direction for direction in DIRECTIONS if direction != target_direction]
    target_pull = _market_pull_item(market_pull_audit, target_direction)
    target_usage = _usage_item(usage_audit, target_direction)
    target_opening_items = _opening_items(opening_board_audit, target_direction)
    evidence: list[str] = []
    contradictions: list[str] = []

    pull_component = (target_pull.pull_percent / 100) if target_pull else 0.0
    if target_pull:
        evidence.append(f"{target_direction}原始拉力={target_pull.pull_percent:.2f}%/{target_pull.pull_label}")
        if target_pull.first_eye_direction:
            evidence.append(f"{target_direction}是市场第一眼方向")
    else:
        contradictions.append(f"{target_direction}缺少原始拉力审计")

    opening_component = _avg_opening_fit(target_opening_items)
    movement_component = _movement_support_score(target_opening_items, target=True)
    if target_opening_items:
        statuses = ",".join(item.position_status for item in target_opening_items)
        actions = ",".join(item.action for item in target_opening_items)
        evidence.append(f"{target_direction}初赔落点={statuses}；后续动作={actions}")
    else:
        contradictions.append(f"{target_direction}缺少核心公司初赔落点")

    topic_component = 0.0
    if target_usage and target_usage.institution_use_status == "USED":
        topic_component += 0.18
        evidence.extend(target_usage.used_evidence[:3])
    elif target_usage and target_usage.available_topics:
        topic_component += 0.08
        contradictions.append(f"{target_direction}有题材但机构使用证据不足")
    else:
        contradictions.append(f"{target_direction}缺少可用题材")

    dispersion_scores: list[float] = []
    for support in supports:
        support_pull = _market_pull_item(market_pull_audit, support)
        support_usage = _usage_item(usage_audit, support)
        support_items = _opening_items(opening_board_audit, support)
        support_score = 0.0
        if support_pull and support_pull.dispersion_available:
            support_score += 0.30
            evidence.append(f"{support}具备分散{target_direction}的市场拉力")
        elif support_pull and support_pull.pull_percent >= 22:
            support_score += 0.18
            evidence.append(f"{support}有中等市场拉力，可部分分散{target_direction}")
        else:
            contradictions.append(f"{support}分散能力不足")
        if support_usage and support_usage.institution_use_status == "USED":
            support_score += 0.22
            evidence.append(f"机构已使用{support}题材")
        if _dominant_action(support_items) == "拉低":
            support_score += 0.14
            evidence.append(f"{support}后续被拉低，具备承接/分流动作")
        dispersion_scores.append(min(support_score, 0.52))

    dispersion_component = sum(dispersion_scores) / max(len(dispersion_scores), 1)
    score = (
        pull_component * 0.24
        + opening_component * 0.24
        + movement_component * 0.16
        + topic_component
        + dispersion_component * 0.32
    )
    score = min(round(score, 4), 1.0)

    opening_fit = "MATCH" if opening_component >= 0.62 else "PARTIAL" if opening_component >= 0.42 else "MISMATCH"
    movement_fit = "MATCH" if movement_component >= 0.65 else "PARTIAL" if movement_component >= 0.48 else "MISMATCH"
    if score >= 0.68 and len(contradictions) <= 2:
        status = "OPTIMAL_FIT"
    elif score >= 0.50:
        status = "BETTER_FIT"
    else:
        status = "UNCONFIRMED"

    return OptimalScenario(
        target_direction=target_direction,
        required_topic_usage=target_usage.available_topics if target_usage else [],
        supporting_directions=supports,
        expected_interval_plan=_scenario_expected_plan(target_direction, expected, opening_board_audit),
        opening_fit=opening_fit,
        movement_fit=movement_fit,
        explanation_score=score,
        contradictions=list(dict.fromkeys(contradictions)),
        evidence=list(dict.fromkeys(evidence)),
        status=status,
    )


def build_optimal_solution_audit(
    *,
    expected: ExpectedOpeningInterval | None,
    market_pull_audit: MarketPullAudit | None,
    opening_board_audit: OpeningBoardAudit | None,
    bookmaker_topic_usage_audit: BookmakerTopicUsageAudit | None,
) -> OptimalSolutionAudit:
    scenarios = [
        _score_scenario(
            direction,
            expected=expected,
            market_pull_audit=market_pull_audit,
            opening_board_audit=opening_board_audit,
            usage_audit=bookmaker_topic_usage_audit,
        )
        for direction in DIRECTIONS
    ]
    audit = OptimalSolutionAudit(scenarios=scenarios)
    if not opening_board_audit or not opening_board_audit.company_audits:
        audit.solution_status = "NO_BET_STRUCTURE"
        audit.notes.append("缺少三项初赔对照，不能模拟机构最优解。")
        return audit

    best = max(scenarios, key=lambda item: item.explanation_score)
    ranked = sorted(scenarios, key=lambda item: item.explanation_score, reverse=True)
    margin = ranked[0].explanation_score - ranked[1].explanation_score if len(ranked) > 1 else ranked[0].explanation_score
    audit.selected_direction = best.target_direction if best.status in {"OPTIMAL_FIT", "BETTER_FIT"} else None

    if best.status == "OPTIMAL_FIT" and margin >= 0.06:
        audit.solution_status = "OPTIMAL_SOLUTION_FOUND"
        audit.better_solution_required = False
        audit.notes.append(f"{best.target_direction}情景解释力最高，且分流项具备承接能力。")
    elif best.status in {"OPTIMAL_FIT", "BETTER_FIT"}:
        audit.solution_status = "BETTER_SOLUTION_ONLY"
        audit.better_solution_required = True
        audit.notes.append("没有完美最优解，只能输出解释力最高的更优解。")
    else:
        audit.solution_status = "NO_OPTIMAL_SOLUTION"
        audit.better_solution_required = False
        audit.notes.append("三项情景都无法低风险解释当前初赔和后续变赔。")
    return audit


def build_future_adjustment_plan(
    *,
    optimal_solution_audit: OptimalSolutionAudit | None,
    opening_board_audit: OpeningBoardAudit | None,
) -> FutureAdjustmentPlan:
    if not optimal_solution_audit or not optimal_solution_audit.selected_direction:
        return FutureAdjustmentPlan(
            target_direction=None,
            notes=["未找到可执行最优解或更优解，不输出后续做盘方向。"],
        )

    target = optimal_solution_audit.selected_direction
    scenario = next(
        item for item in optimal_solution_audit.scenarios if item.target_direction == target
    )
    plan = FutureAdjustmentPlan(
        target_direction=target,
        notes=[
            f"当前按{optimal_solution_audit.solution_status}生成后续做盘方向。",
            "后续方向是机构动作预期，不等同投注建议。",
        ],
    )
    for direction in DIRECTIONS:
        items = _opening_items(opening_board_audit, direction)
        action = _dominant_action(items)
        interval = scenario.expected_interval_plan.get(direction, "心理区间未确认")
        if direction == target:
            if action == "抬高":
                recommended = "稳定/不再大幅抬高"
                purpose = "利用其它两项分流目标方向热度，同时保持目标项可承载。"
            elif action == "拉低":
                recommended = "稳定在低位或小幅回调"
                purpose = "控赔并维持目标方向信心。"
            else:
                recommended = "稳定"
                purpose = "保持目标项在心理区间内承接。"
            not_hit = None
        else:
            recommended = "拉低/维持可接受度" if action != "拉低" else "维持分流位"
            purpose = f"作为{target}的分流或阻挡项，吸收市场注意力。"
            not_hit = f"{direction}当前作为协助分流项，不是本轮最优解目标。"
        plan.items.append(
            FutureAdjustmentItem(
                direction=direction,
                recommended_action=recommended,
                target_psychological_interval=interval,
                purpose=purpose,
                not_expected_to_hit_reason=not_hit,
            )
        )
    return plan


def build_final_structure_judgement(
    *,
    optimal_solution_audit: OptimalSolutionAudit | None,
) -> FinalStructureJudgement:
    if not optimal_solution_audit:
        return FinalStructureJudgement(
            status="NO_BET_STRUCTURE",
            direction=None,
            reason="最优解审计未生成。",
            confidence="低",
        )
    if optimal_solution_audit.solution_status == "OPTIMAL_SOLUTION_FOUND":
        return FinalStructureJudgement(
            status="EXECUTE",
            direction=optimal_solution_audit.selected_direction,
            reason="找到机构最优解：目标方向、分流方向、初赔落点和后续动作具备闭合解释。",
            confidence="中高",
            warnings=list(optimal_solution_audit.notes),
        )
    if optimal_solution_audit.solution_status == "BETTER_SOLUTION_ONLY":
        return FinalStructureJudgement(
            status="BETTER_SOLUTION_ONLY",
            direction=optimal_solution_audit.selected_direction,
            reason="没有完美最优解，但存在解释力最高的更优解；允许输出结构方向，必须说明风险。",
            confidence="中",
            warnings=list(optimal_solution_audit.notes),
        )
    if optimal_solution_audit.solution_status == "NO_OPTIMAL_SOLUTION":
        return FinalStructureJudgement(
            status="NO_OPTIMAL_SOLUTION",
            direction=None,
            reason="三项情景都不能低风险解释当前做盘，机构没有清晰最优解。",
            confidence="低",
            warnings=list(optimal_solution_audit.notes),
        )
    return FinalStructureJudgement(
        status="NO_BET_STRUCTURE",
        direction=None,
        reason="结构混乱或关键审计缺失，不能输出执行方向。",
        confidence="低",
        warnings=list(optimal_solution_audit.notes),
    )
