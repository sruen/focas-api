from __future__ import annotations

from typing import Iterable

from .models import CompanyOdds, MatchContext, NaturalPull, OriginalBookMode, PipelineResult, StrengthContext
from .odds_system import normalize_company
from .config import HARD_DATA_SOURCE

DIRECTIONS = ("主胜", "平局", "客胜")
HARD_COMPANIES = {"William", "Ladbrokes"}


def _safe(value: object, fallback: str = "未提供") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _yn(value: object) -> str:
    return "是" if value is True else "否" if value is False else _safe(value)


def _join(values: Iterable[str] | None, fallback: str = "无") -> str:
    items = [str(value) for value in (values or []) if str(value).strip()]
    return "、".join(items) if items else fallback


def _number(value: object, digits: int = 3, fallback: str = "-") -> str:
    if value is None:
        return fallback
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return _safe(value, fallback)


def _pull_map(pulls: list[NaturalPull]) -> dict[str, NaturalPull]:
    return {pull.direction: pull for pull in pulls}


def _is_stop_report(result: PipelineResult) -> bool:
    return (
        result.stop
        or result.report_mode == "STOP_REPORT_ONLY"
        or result.basic_context_status == "INCOMPLETE"
        or result.table_read_confirmed == "NO"
        or result.odds_analysis_status == "FORBIDDEN"
        or result.mainline_output_status == "FORBIDDEN"
    )


def _render_stop_report(result: PipelineResult) -> str:
    missing = result.missing_fields or ["当前停止节点所需真实资料未完整提供"]
    lines = [
        "# FOCAS STOP_REPORT_ONLY",
        "",
        "## 停止节点",
        f"- {_safe(result.stop_node, '流程硬闸门')}",
        "",
        "## 停止原因",
        f"- {_safe(result.stop_reason, '硬闸门未通过，禁止继续生成正式比赛分析。')}",
        "",
        "## 缺失字段清单",
        *[f"- {item}" for item in missing],
        "",
        "## 为什么不能继续",
        "- 当前输入没有通过完整事实校验，模板字段、缺失字段或未完成的表内审计不能作为比赛事实使用。",
        "- 根据 v1.7 规则，赔率解释与单一结构方向必须在硬闸门全部通过后生成。",
        "",
        "## 下一步需要补什么",
        "- 补齐停止节点列出的真实资料，并重新运行完整流程。",
        "- 若停止在现代骨架查表，需提供可读取的数据源并确保 William 与 Ladbrokes 均按各自返还率体系完成骨架查表。",
        "",
        "## 当前禁止项",
        f"- Hard_Data_Source = {HARD_DATA_SOURCE}",
        f"- Basic_Context_Status = {result.basic_context_status}",
        f"- TABLE_READ_CONFIRMED = {result.table_read_confirmed}",
        "- Odds_Analysis = FORBIDDEN",
        "- Mainline_Output = FORBIDDEN",
        "- Betting_Permission = NO",
        "- Signal_Permission = NO",
        "- Formal_Prediction = NO",
    ]
    return "\n".join(lines) + "\n"


def _odds_fact_line(item: CompanyOdds) -> str:
    return (
        f"| {item.company} | {item.initial.home:.2f} / {item.initial.draw:.2f} / {item.initial.away:.2f} | "
        f"{item.current.home:.2f} / {item.current.draw:.2f} / {item.current.away:.2f} | "
        f"{item.current.home - item.initial.home:+.2f} / {item.current.draw - item.initial.draw:+.2f} / "
        f"{item.current.away - item.initial.away:+.2f} |"
    )


def _conversion_lines(result: PipelineResult) -> list[str]:
    lines = [
        "| 公司 | 时点 | 机构原始赔率 | calculated_return_rate | 识别体系 | system_distance | 骨架表路由 | 数值转换 | system_lookup_status |",
        "|---|---|---|---:|---|---:|---|---|---|",
    ]
    for item in result.odds_system_conversions:
        lines.append(
            f"| {item.company} | {item.snapshot_type} | "
            f"{item.raw_home:.3f} / {item.raw_draw:.3f} / {item.raw_away:.3f} | "
            f"{item.raw_payout_percent:.3f}% | {item.detected_system} | {item.system_distance:.4f} | "
            f"{item.target_system} 对应 sheet | 不转换，保留原始赔率 | "
            f"{item.system_lookup_status} |"
        )
    return lines


def _low_coordinates(result: PipelineResult, hard_only: bool) -> list:
    coordinates = getattr(result, "odds_coordinates", None)
    if not coordinates:
        return []
    rows = []
    for company_set in coordinates.company_sets:
        company = normalize_company(company_set.company)
        if (company in HARD_COMPANIES) != hard_only:
            continue
        for item in company_set.coordinates:
            if item.is_snapshot_low:
                rows.append(item)
    return rows


def _lookup_lines(result: PipelineResult, *, hard_only: bool) -> list[str]:
    lines = [
        "| 公司 | 时点 | 赔率 | 返还率 | 识别体系 | 最低项 | 主赔轴区间 | 水位 | 主赔轴赔率 | 实际最低赔率 | 边界距离 | 落点状态 | lookup_status |",
        "|---|---|---|---:|---|---|---|---|---:|---:|---:|---|---|",
    ]
    rows = _low_coordinates(result, hard_only)
    for item in rows:
        crossed = "否" if item.deviation == "表内" else "是"
        lines.append(
            f"| {item.company} | {'初赔' if item.time_point == 'initial' else '最新'} | "
            f"{item.odds_home:.3f} / {item.odds_draw:.3f} / {item.odds_away:.3f} | {item.return_rate:.3f}% | "
            f"{item.system} | {item.direction} | {_safe(item.interval_id)} | {_safe(item.water_band)} | "
            f"{_number(item.table_axis_odds)} | {item.actual_low_odds:.3f} | "
            f"{_number(item.boundary_distance, 4)} | {item.deviation} | {item.lookup_status} |"
        )
    if not rows:
        lines.append("| 无 | - | - | - | - | - | - | - | - | - | - | - | NO_TABLE_ROW |")
    return lines


def _range_label(lower: float | None, upper: float | None) -> str:
    if lower is None or upper is None:
        return "未确认"
    return f"{lower:.3f}-{upper:.3f}"


def _deviation_label(value: float | None) -> str:
    return f"{value:+.3f}" if value is not None else "未确认"


def _opening_skeleton_audit_lines(result: PipelineResult) -> list[str]:
    interval_audit = result.interval_audit
    if not interval_audit or not interval_audit.audits:
        return ["- 初赔合理性审计未生成。未完成该步骤时，不得解释机构动机。"]

    expected = interval_audit.expected
    lines = [
        f"- P4 理论骨架：{_safe(getattr(expected, 'expected_interval', None))}。来源：{_safe(getattr(expected, 'expected_interval_source', None))}。",
        "- 审计顺序：先识别机构初赔返还率体系，再读取该体系工作表中的理论区间赔率，最后比较机构发布的原始初赔。赔率数值不做二次转换。未确认骨架时，不得解释机构动机。",
        "- 平赔和负赔是机构档口参考范围；主赔是骨架精确调用范围。",
        "",
        "| 公司 | 初赔体系 | 理论区间 | 理论主赔范围 | 平赔档口参考 | 负赔档口参考 | 机构原始初赔 | 实际最近区间 | 主赔偏差 | 平赔参考偏差 | 负赔参考偏差 | 主赔合理性 | 审计状态 |",
        "|---|---|---:|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for item in interval_audit.audits:
        raw_opening = (
            f"{item.raw_opening_home:.3f} / {item.raw_opening_draw:.3f} / "
            f"{item.raw_opening_away:.3f}"
            if (
                item.raw_opening_home is not None
                and item.raw_opening_draw is not None
                and item.raw_opening_away is not None
            )
            else "未确认"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    item.company,
                    item.system or "未确认",
                    str(item.expected_interval_id) if item.expected_interval_id is not None else "未确认",
                    _range_label(item.expected_home_min, item.expected_home_max),
                    _range_label(item.expected_draw_reference_min, item.expected_draw_reference_max),
                    _range_label(item.expected_away_reference_min, item.expected_away_reference_max),
                    raw_opening,
                    str(item.opening_interval_id) if item.opening_interval_id is not None else "未确认",
                    _deviation_label(item.home_range_deviation),
                    _deviation_label(item.draw_reference_deviation),
                    _deviation_label(item.away_reference_deviation),
                    item.price_reasonableness,
                    item.hard_status,
                ]
            )
            + " |"
        )
    return lines


def _motive_lines(result: PipelineResult) -> list[str]:
    stage = result.stage_9_analysis
    if not stage:
        return ["- 赔率动作解释未生成。"]
    lines = [
        f"- 三项组合赔面：{stage.odds_face_shape}",
        f"- William / Ladbrokes 确认关系：{_safe(getattr(stage.company_relation, 'relation_type', None))}",
        "- 初赔先判断机构是否利用基本面、主场或客场第一眼拉力，再解释后续变赔。",
        "- 抬高 / 拉低只是动作。动作必须通过信心承载、分散有效性、自然拉力、表内区间和公司目的五道门。",
    ]
    opening = [
        item
        for item in getattr(stage, "opening_motive_chain", []) or []
        if normalize_company(item.company) in HARD_COMPANIES
    ]
    if opening:
        lines.append("- 初赔目的链：")
        for item in opening:
            lines.append(
                f"  - {item.company}：初赔低赔方向={item.direction}；现实区间={_safe(item.opening_interval_id)}；"
                f"P4理论区间={_safe(item.expected_interval_id)}；区间差={_safe(item.interval_delta)}；"
                f"自然拉力={item.natural_pull}；原始压力={item.original_pressure}；"
                f"利用基本面或主客场拉力={'是' if item.uses_fundamental_pull else '未形成明确证据'}；"
                f"初赔目的={item.motive_type}；后续约束={item.selection_constraint}。"
            )
    for company in ("William", "Ladbrokes"):
        readings = [
            item for item in stage.action_motive_chain
            if normalize_company(item.company) == company
        ]
        lines.append(f"- {company} 公司目的链：")
        for item in readings:
            lines.append(
                f"  - {item.direction}{item.action}：{item.company_purpose}。"
                f"自然拉力={_safe(item.natural_pull)}；信心承载={item.confidence_carrying}；"
                f"分散有效性={item.dispersion_effectiveness}；表内位置={item.table_interval_position}；"
                f"分散对象={_safe(item.dispersion_target)}；保护对象={_safe(item.protected_direction)}；"
                f"打击对象={_safe(item.attacked_direction)}。{item.odds_move_semantics}"
            )
    return lines


def _integrated_lines(result: PipelineResult) -> list[str]:
    judgement = result.integrated_structure
    if not judgement:
        return ["- 综合结构正文未生成。"]
    return [
        f"- 主胜：{judgement.home_integrated_judgement}",
        f"- 平局：{judgement.draw_integrated_judgement}",
        f"- 客胜：{judgement.away_integrated_judgement}",
    ]


def _narrative_audit_lines(result: PipelineResult) -> list[str]:
    audit = result.narrative_audit
    if not audit:
        return ["- 三项题材审计未生成。"]
    lines = [
        f"- 题材数据模式：{audit.source_mode}",
        f"- 来源级审计完整：{'是' if audit.complete else '否'}",
        "- 规则：题材存在 != 影响市场；影响市场 != 机构利用；机构利用 != 比赛结果命中。",
    ]
    for item in audit.direction_audits:
        lines.append(
            f"- {item.direction}：题材={_join(item.available_topics)}；可见度={item.visibility}；"
            f"强度={item.strength}；与实力关系={item.strength_alignment}；"
            f"机构利用={item.institution_use_status}；利用证据={_join(item.institution_use_evidence)}"
        )
    return lines


def _scenario_audit_lines(result: PipelineResult) -> list[str]:
    audit = result.scenario_audit
    if not audit:
        return ["- 三情景反推未生成。"]
    lines = [
        f"- 决策状态：{audit.decision_status}",
        f"- 主情景：{_safe(audit.main_scenario)}；备选情景：{_safe(audit.alternative_scenario)}",
        f"- 最大矛盾：{_safe(audit.max_contradiction)}",
    ]
    for item in audit.scenarios:
        lines.append(
            f"- {item.direction}情景：状态={item.status}；机构利用证据={_join(item.institution_use_evidence)}；"
            f"矛盾={_join(item.contradictions)}；失效检查={_join(item.invalidation_conditions)}"
        )
    return lines


def _backend_audit_lines(result: PipelineResult) -> list[str]:
    return [
        "",
        "## 后台审计附录",
        f"- Basic_Context_Status={result.basic_context_status}",
        f"- TABLE_READ_CONFIRMED={result.table_read_confirmed}",
        f"- Odds_Analysis={result.odds_analysis_status}",
        f"- Mainline_Output={result.mainline_output_status}",
        f"- Strength_Source={result.strength_source}",
        f"- report_mode={result.report_mode}",
        f"- Hard_Data_Source={HARD_DATA_SOURCE}",
        f"- EXPECTED_INTERVAL_STATUS={result.expected_interval_status}",
        "",
        "### P4 内置 strength interval bridge 理论区间",
        f"- {result.interval_audit.expected if result.interval_audit else '无'}",
        "",
        "### 返还率体系识别与骨架表路由明细",
        *_conversion_lines(result),
    ]


def render_frontend_report(
    *,
    match: MatchContext,
    strength: StrengthContext,
    pulls: list[NaturalPull],
    book_mode: OriginalBookMode,
    odds: list[CompanyOdds],
    result: PipelineResult,
    backend_audit: bool = False,
) -> str:
    if _is_stop_report(result):
        return _render_stop_report(result)

    pull_map = _pull_map(pulls)
    distribution = result.original_distribution
    integrated = result.integrated_structure
    relative = result.relative_selection
    book_mode = result.book_mode_context or book_mode
    expected = result.interval_audit.expected if result.interval_audit else None
    strength = result.strength_context or strength
    strength_note = (
        "广义实力来自输入包人工校准。"
        if result.strength_source == "USER_PROVIDED"
        else "广义实力为辅助估算，不替代人工校准。"
    )
    lines = [
        f"# FOCAS 中文读盘报告｜{match.home_team} vs {match.away_team}",
        "",
        "## 1. 先说人话",
        f"本场先以真实基本面确认双方关系，再用原始分布解释市场天然压力，最后按 William 与 Ladbrokes 各自返还率体系读取现代骨架区间，并比较机构原始赔率。",
        (
            f"当前决策状态={result.decision_status}；正式结构输出={result.final_direction}；"
            f"观察倾向={_safe(result.structural_lean)}。这是结构分析，不是投注建议。"
        ),
        "",
        "## 2. 基本面事实",
        f"- Hard_Data_Source：{HARD_DATA_SOURCE}",
        f"- 比赛：{match.home_team} vs {match.away_team}",
        f"- 赛事：{_safe(match.competition)}｜时间：{_safe(match.kickoff_time)}｜阶段：{_safe(match.stage)}",
        f"- 中立场：{_yn(match.neutral_venue)}｜单回合：{_yn(match.single_leg)}｜比赛类型：{_safe(match.match_type)}",
        f"- 加时 / 点球规则：{_safe(match.extra_time_or_penalties)}｜真实主客属性：{_yn(match.real_home_away)}",
        f"- Strength_Source：{result.strength_source}。{strength_note}",
        f"- 广义实力：主队={_safe(strength.home_grade)}｜客队={_safe(strength.away_grade)}｜"
        f"静态档位差={_safe(strength.static_gap)}｜动态修正={_safe(strength.dynamic_adjustment)}｜最终动态关系={_safe(strength.final_gap)}",
        f"- P4 理论区间：内置 strength interval bridge｜状态={result.expected_interval_status}｜"
        f"键={_safe(getattr(expected, 'p4_strength_key', None))}｜来源={_safe(getattr(expected, 'expected_interval_source', None))}｜"
        f"匹配表={_safe(getattr(expected, 'matched_sheet', None))}｜匹配行={_safe(getattr(expected, 'matched_row_id', None))}｜"
        f"区间={_safe(getattr(expected, 'expected_interval', None))}",
        f"- 赛事语义修正：{result.context_modifiers.summary() if result.context_modifiers else '未生成'}",
        "",
        "## 3. 近况",
        "| 项目 | 主队 | 客队 |",
        "|---|---|---|",
    ]
    for label, attr in (
        ("排名 / 积分", "rank"),
        ("近 5-6 场", "recent_matches"),
        ("场地适应", "venue_adaptation"),
        ("进攻状态", "attack_state"),
        ("防守状态", "defense_state"),
        ("近期重大比赛", "major_recent_matches"),
    ):
        home_value = getattr(match.home, attr)
        away_value = getattr(match.away, attr)
        if attr == "rank":
            home_value = f"{home_value} / {match.home.points}"
            away_value = f"{away_value} / {match.away.points}"
        lines.append(f"| {label} | {_safe(home_value)} | {_safe(away_value)} |")

    lines.extend(["", "## 4. 往绩"])
    for label, attr in (
        ("总体交锋", "overall"),
        ("近年交锋", "recent_years"),
        ("同赛事交锋", "same_competition"),
        ("主客 / 中立场交锋", "venue_specific"),
        ("最近一次关键交锋", "latest_key_match"),
        ("往绩对市场心理的影响", "market_psychology"),
    ):
        lines.append(f"- {label}：{_safe(getattr(match.h2h, attr))}")

    lines.extend([
        "",
        "## 5. 伤停 / 阵容",
        f"- 主队：{match.home.injuries}",
        f"- 客队：{match.away.injuries}",
        "",
        "## 6. 战意 / 赛程",
        f"- 主队：战意={match.home.motivation}｜赛程体能={match.home.schedule_fatigue}",
        f"- 客队：战意={match.away.motivation}｜赛程体能={match.away.schedule_fatigue}",
        "",
        "## 7. 三项自然拉力",
    ])
    for direction in DIRECTIONS:
        pull = pull_map[direction]
        lines.append(
            f"- {direction}：{pull.strength}｜事实={pull.facts}｜市场心理={pull.market_psychology}｜"
            f"容易受注={_yn(pull.easy_to_receive)}｜大众第一眼={_yn(pull.first_eye_direction)}"
        )
    lines.extend([
        "- 自然拉力不是方向结论：强不能直接确认，弱不能直接排除。",
        f"- 原始分布：{distribution.distribution_type}｜主胜压力={distribution.home_pressure}｜"
        f"平局压力={distribution.draw_pressure}｜客胜压力={distribution.away_pressure}｜"
        f"市场第一眼={_safe(distribution.first_eye_direction)}",
        f"- 原始分布理由：{_join(distribution.reasoning)}",
        "",
        "## 8. 原书思维模式",
        f"- 本场原书模式：{book_mode.mode}",
        f"- 挂接原因：{book_mode.reason}",
        f"- 最需要观察的赔率项：{book_mode.key_odds_to_watch}",
        f"- 最容易误读的位置：{book_mode.easiest_misread}",
        f"- 来源区分：{_join(book_mode.source_classification)}",
        "",
        "## 9. William / Ladbrokes / Avg 赔率事实",
        "| 公司 | 初赔 | 最新赔率 | 原始变化 |",
        "|---|---|---|---|",
        *[_odds_fact_line(item) for item in odds],
        "- Avg 只能作为市场背景，不能替代 William / Ladbrokes。",
        "",
        "### 返还率体系识别与骨架表路由",
        *_conversion_lines(result),
        "- 赔率数值不做二次转换。先识别体系并路由到对应骨架表，再比较机构原始赔率。",
        "",
        "## 10. 现代骨架区间查表",
        "### 【硬判断公司】William / Ladbrokes",
        *_lookup_lines(result, hard_only=True),
        "",
        "### 【市场背景】Avg",
        *_lookup_lines(result, hard_only=False),
        "- 现实赔率落点实际读取新版 xlsx；P4 内置桥接表不冒充现实赔率数据源。Avg 不参与硬判断公司补位。",
        "",
        "### 初赔合理性审计：理论骨架 vs 机构实际初赔",
        *_opening_skeleton_audit_lines(result),
        "",
        "## 11. 当前赔面对胜 / 平 / 负是否有利",
        *_motive_lines(result),
        "",
        "### 综合结构正文",
        *_integrated_lines(result),
        "",
        "### 三项题材审计",
        *_narrative_audit_lines(result),
        "",
        "### 主胜 / 平局 / 客胜三情景反推",
        *_scenario_audit_lines(result),
        "",
        "## 12. 不利方向排除",
        f"- 明确不利排除方向：{_join(integrated.adverse_excluded_directions)}",
        f"- 支持链未闭合但不能排除的方向：{_join(integrated.unconfirmed_directions)}",
        "- 只有完整证据链形成的“不利”才能排除方向。支持不足不等于不利。",
        "",
        "## 13. 第二阶段相对主线选择",
        *(
            [
                f"- 明确不利排除方向：{_join(relative.adverse_exclusions)}",
                f"- 未被不利排除但相对结构强度较弱：{_join(relative.relative_non_selected)}",
                f"- 第二阶段选择：{relative.selected_direction}｜置信度={relative.confidence}",
                "- 第二阶段只做相对结构强弱选择，不重新制造不利排除。",
                *[f"- {note}" for note in relative.notes],
            ]
            if relative
            else ["- 已有两个方向被完整不利证据链排除，无需进入第二阶段相对比较。"]
        ),
        "",
        "## 14. 最终结构方向",
        f"- 决策状态：{result.decision_status}",
        f"- 最终结构方向：{result.final_direction}",
        f"- 仅供观察的结构倾向：{_safe(result.structural_lean)}",
        "",
        "## 15. 结论",
        (
            f"- 当前赔率结构层正式输出为 {result.final_direction}。"
            if result.final_direction != "PASS"
            else "- 当前证据链不足，正式输出为 PASS；观察倾向不得包装为单一方向。"
        ),
        "- 本报告只输出结构分析，不输出投注建议、买入建议、主推、稳胆、资金分配、自动信号或正式预测包装。",
    ])
    if backend_audit:
        lines.extend(_backend_audit_lines(result))
    return "\n".join(lines).strip() + "\n"
