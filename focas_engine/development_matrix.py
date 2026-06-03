from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import (
    CompanyOdds,
    ExpectedOpeningInterval,
    OpeningBoardAudit,
    OriginalDistribution,
    OriginalDistributionAudit,
    PreOddsPredictedOddsAudit,
    StrengthContext,
    StrengthDynamicAudit,
    ThreeDirectionDevelopmentMatrixItem,
)
from .strength import GRADE_ORDER


DIRECTIONS = ("主胜", "平局", "客胜")
GRADE_SET = set(GRADE_ORDER)


def build_strength_dynamic_audit(
    *,
    strength: StrengthContext,
    expected: ExpectedOpeningInterval | None,
    estimate: Any | None = None,
) -> StrengthDynamicAudit:
    """Expose original-book broad-strength grades and dynamic bridge output.

    This audit deliberately only reports backend/original-book grades. It does
    not infer or create new strength labels for GPT output.
    """

    home_grade = (strength.home_grade or "").strip() or None
    away_grade = (strength.away_grade or "").strip() or None
    notes: list[str] = []
    ok = bool(home_grade in GRADE_SET and away_grade in GRADE_SET)
    if not ok:
        notes.append("广义实力档位缺失或非法，GPT 不得自创档位或进入精确开发赔率判断。")

    final_gap_value = getattr(expected, "final_gap_value", None) if expected else None
    final_gap_label = getattr(expected, "final_gap_label", None) if expected else None
    expected_low_side = getattr(expected, "expected_low_side", None) if expected else None
    expected_interval = getattr(expected, "expected_interval", None) if expected else None

    if expected_interval:
        interpretation = (
            f"原书档位={home_grade or '未确认'} vs {away_grade or '未确认'}；"
            f"动态关系={final_gap_label or strength.final_gap or '未确认'}；"
            f"理论低赔方向={expected_low_side or '未确认'}；理论区间={expected_interval}。"
            "该字段只说明广义实力与骨架桥接，不等于最终结构方向。"
        )
    else:
        interpretation = (
            f"原书档位={home_grade or '未确认'} vs {away_grade or '未确认'}；"
            "理论区间未确认，GPT 不得自行补骨架。"
        )

    return StrengthDynamicAudit(
        home_grade=home_grade,
        away_grade=away_grade,
        allowed_grades=list(GRADE_ORDER),
        static_gap=getattr(expected, "static_strength_gap", None) if expected else strength.static_gap,
        dynamic_adjustment=getattr(expected, "dynamic_adjustment", None) if expected else strength.dynamic_adjustment,
        final_gap=getattr(expected, "final_dynamic_strength_relation", None) if expected else strength.final_gap,
        final_gap_value=final_gap_value,
        final_gap_label=final_gap_label,
        expected_low_side=expected_low_side,
        expected_interval=expected_interval,
        interpretation=interpretation,
        ok=ok and expected is not None,
        notes=notes,
    )


def _scenario_constraints(distribution: OriginalDistribution | None) -> list[str]:
    if distribution is None:
        return ["原始分布缺失，禁止跳到最终方向。"]

    dtype = distribution.distribution_type or "UNCONFIRMED"
    if dtype == "胜负原始双分":
        return [
            "主胜目标必须解释客胜强拉力是否被机构利用来分流主胜。",
            "平局目标必须解释胜负两端是否共同保留承接来分流平局。",
            "客胜目标必须解释主胜强拉力是否被机构利用来分流客胜。",
        ]
    if dtype == "胜平原始合力":
        return [
            "主胜目标必须解释平局合力是否被用于遮蔽或分流。",
            "平局目标必须解释主胜合力是否被用于分流。",
            "客胜目标必须解释为何在胜平合力下仍有客胜承接。",
        ]
    if dtype == "平负原始合力":
        return [
            "主胜目标必须解释为何能对抗平负原始合力。",
            "平局目标必须解释客胜合力是否保留分流。",
            "客胜目标必须解释平局合力是否保留分流。",
        ]
    if dtype == "三项分散":
        return [
            "三项目标均必须解释另外两项是否仍具备分流能力。",
            "任何方向不能只因自身赔率动作有利而成立。",
        ]
    if dtype == "单向主胜拉力":
        return [
            "主胜目标必须解释如何降热或遮蔽单向主胜拉力。",
            "平局/客胜目标必须解释如何对抗主胜单向拉力。",
        ]
    if dtype == "单向客胜拉力":
        return [
            "客胜目标必须解释如何降热或遮蔽单向客胜拉力。",
            "主胜/平局目标必须解释如何对抗客胜单向拉力。",
        ]
    if dtype == "平局天然拉力":
        return [
            "平局目标必须解释胜负两端是否有足够分流。",
            "胜负目标必须解释如何处理平局天然拉力。",
        ]
    return [
        f"原始分布={dtype}，三项目标均需先解释基本面题材、分流项与现盘动作是否闭合。"
    ]


def build_original_distribution_audit(
    *, distribution: OriginalDistribution | None
) -> OriginalDistributionAudit:
    if distribution is None:
        return OriginalDistributionAudit(
            distribution_type="MISSING",
            scenario_constraints=["原始分布缺失，禁止输出最终方向。"],
            reasoning=["原始分布对象未生成。"],
        )

    return OriginalDistributionAudit(
        distribution_type=distribution.distribution_type,
        home_pressure=distribution.home_pressure,
        draw_pressure=distribution.draw_pressure,
        away_pressure=distribution.away_pressure,
        first_eye_direction=distribution.first_eye_direction,
        weak_confidence_directions=list(distribution.weak_confidence_directions),
        dispersion_available=dict(distribution.dispersion_available),
        scenario_constraints=_scenario_constraints(distribution),
        reasoning=list(distribution.reasoning),
    )


def build_pre_odds_predicted_odds_audit(
    *,
    formula_confirmed: bool = False,
    scenario_predictions: list[dict[str, Any]] | None = None,
) -> PreOddsPredictedOddsAudit:
    if not formula_confirmed:
        return PreOddsPredictedOddsAudit(
            calculation_status="MISSING_FORMULA",
            formula_source="MANUAL_REVIEW_REQUIRED",
            gpt_may_generate_exact_odds=False,
            scenario_predictions=[],
            notes=[
                "精确开发赔率公式未接入，GPT 禁止自行生成精确预测赔率。",
                "当前只能输出骨架区间、开发逻辑与采用程度；不得编单点赔率。",
            ],
        )

    return PreOddsPredictedOddsAudit(
        calculation_status="FORMULA_CONFIRMED",
        formula_source="ORIGINAL_BOOK_SKELETON_FORMULA",
        gpt_may_generate_exact_odds=True,
        scenario_predictions=scenario_predictions or [],
        notes=["精确开发赔率来自原书骨架公式，GPT 可引用但不得改写。"],
    )


def _company_key(company: str) -> str | None:
    raw = (company or "").lower()
    if "william" in raw or "威廉" in company:
        return "William"
    if "ladbrokes" in raw or "立博" in company:
        return "Ladbrokes"
    return None


def _actual_odds(odds: list[CompanyOdds]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in odds:
        key = _company_key(item.company)
        if not key:
            continue
        out[key] = f"{item.current.home:.2f}/{item.current.draw:.2f}/{item.current.away:.2f}"
    return out


def _actions(opening_board_audit: OpeningBoardAudit | None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {direction: [] for direction in DIRECTIONS}
    if not opening_board_audit:
        return out
    for company in opening_board_audit.company_audits:
        for item in company.direction_audits:
            if item.direction in out:
                out[item.direction].append(item.action)
    return out


def _over_raised_away(opening_board_audit: OpeningBoardAudit | None) -> bool:
    if not opening_board_audit:
        return False
    over_count = 0
    for company in opening_board_audit.company_audits:
        for item in company.direction_audits:
            if item.direction == "客胜" and item.expected_max is not None and item.current_odds > item.expected_max:
                over_count += 1
    return over_count >= 1


def _count(actions: dict[str, list[str]], direction: str, action: str) -> int:
    return actions.get(direction, []).count(action)


def _development_logic(target: str, distribution: OriginalDistribution | None) -> str:
    dtype = distribution.distribution_type if distribution else "UNCONFIRMED"
    if target == "主胜":
        if dtype == "胜负原始双分":
            return "主胜维持或略抬至心理区间高水，打击主队信心；平局下拉；客胜下拉或维持，利用客队强拉力营造客队不败。"
        return "主胜目标需避免自身过热，并利用平局/客胜题材分流。"
    if target == "平局":
        if dtype == "胜负原始双分":
            return "主胜保留承接；平局稳中小降；客胜保留承接，让平局藏在胜负双强中间。"
        return "平局目标需依赖胜负两端分流，并保持平赔可承接但不过度暴露。"
    if target == "客胜":
        if dtype == "胜负原始双分":
            return "主胜下拉吸收主队名气；平局下拉吸收友谊赛题材；客胜维持表内高水或小幅抬高，但不能失去承接。"
        return "客胜目标需利用主胜和平局分流，客赔可制造阻力但不得脱离承接区。"
    return "UNCONFIRMED"


def _constraint_text(
    *,
    target: str,
    strength_audit: StrengthDynamicAudit | None,
    distribution_audit: OriginalDistributionAudit | None,
) -> str:
    grades = "档位未确认"
    if strength_audit and strength_audit.home_grade and strength_audit.away_grade:
        grades = f"{strength_audit.home_grade} vs {strength_audit.away_grade}"
    dtype = distribution_audit.distribution_type if distribution_audit else "原始分布未确认"
    constraints = (distribution_audit.scenario_constraints if distribution_audit else []) or []
    for item in constraints:
        if item.startswith(target):
            return f"{grades}；{dtype}；{item}"
    return f"{grades}；{dtype}；{target}目标必须解释另外两项分流是否闭合。"


def _predicted_odds_placeholder(pre_odds_audit: PreOddsPredictedOddsAudit | None) -> dict[str, Any]:
    if pre_odds_audit and pre_odds_audit.gpt_may_generate_exact_odds:
        return {
            "calculation_status": pre_odds_audit.calculation_status,
            "scenario_predictions": [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in pre_odds_audit.scenario_predictions],
        }
    return {
        "calculation_status": "MISSING_FORMULA",
        "exact_odds": None,
        "gpt_may_generate_exact_odds": False,
        "allowed_reference": "只能引用 psychological_interval_audit 的骨架区间；禁止 GPT 自行生成单点开发赔率。",
    }


def _adoption_and_conclusion(
    *,
    target: str,
    distribution: OriginalDistribution | None,
    opening_board_audit: OpeningBoardAudit | None,
) -> tuple[str, str, list[str]]:
    acts = _actions(opening_board_audit)
    notes: list[str] = []
    home_down = _count(acts, "主胜", "拉低") >= 2
    draw_down = _count(acts, "平局", "拉低") >= 2
    away_up = _count(acts, "客胜", "抬高") >= 2
    away_over = _over_raised_away(opening_board_audit)

    dtype = distribution.distribution_type if distribution else ""
    if target == "主胜":
        if dtype == "胜负原始双分" and (home_down and away_up):
            return (
                "NOT_ADOPTED",
                "主胜最优开发路径未被采用：现实盘压低主胜并抬高客胜，没有利用客胜强拉力分流主胜，主胜应降级或排除。",
                notes,
            )
        if home_down:
            return ("PARTIAL_ADOPTED", "主胜题材被使用，但仍需检查另外两项是否保留分流。", notes)
        return ("UNCONFIRMED", "主胜开发路径未确认。", notes)

    if target == "平局":
        if draw_down and home_down and away_up:
            return (
                "PARTIAL_ADOPTED",
                "平局开发组合被部分采用：胜平侧被压低，但客胜分流被削弱，平局不是完美最优。",
                notes,
            )
        if draw_down:
            return ("PARTIAL_ADOPTED", "平局题材被使用，但胜负两端分流是否闭合仍需审计。", notes)
        return ("UNCONFIRMED", "平局开发路径未确认。", notes)

    if target == "客胜":
        if home_down and draw_down and away_up:
            status = "PARTIAL_OR_OVER_RAISED" if away_over else "PARTIAL_ADOPTED"
            conclusion = (
                "客胜目标只被部分采用：主平下拉可分流客胜，但客胜被抬高过度或承接不足，更像降热/阻挡，客胜降级。"
                if away_over
                else "客胜目标部分采用：主平下拉可分流，仍需确认客胜是否保留承接。"
            )
            return (status, conclusion, notes)
        if away_up:
            return ("OVER_RAISED_REVIEW", "客胜被抬高，需区分保护、阻挡、降热或放弃。", notes)
        return ("UNCONFIRMED", "客胜开发路径未确认。", notes)

    return ("UNCONFIRMED", "未知目标方向。", notes)


def build_three_direction_development_matrix(
    *,
    strength_audit: StrengthDynamicAudit | None,
    distribution: OriginalDistribution | None,
    distribution_audit: OriginalDistributionAudit | None,
    pre_odds_audit: PreOddsPredictedOddsAudit | None,
    opening_board_audit: OpeningBoardAudit | None,
    odds: list[CompanyOdds],
) -> list[ThreeDirectionDevelopmentMatrixItem]:
    actual = _actual_odds(odds)
    items: list[ThreeDirectionDevelopmentMatrixItem] = []
    for target in DIRECTIONS:
        adoption_status, conclusion, notes = _adoption_and_conclusion(
            target=target,
            distribution=distribution,
            opening_board_audit=opening_board_audit,
        )
        items.append(
            ThreeDirectionDevelopmentMatrixItem(
                target_direction=target,
                strength_and_distribution_constraint=_constraint_text(
                    target=target,
                    strength_audit=strength_audit,
                    distribution_audit=distribution_audit,
                ),
                optimal_development_logic=_development_logic(target, distribution),
                predicted_odds=_predicted_odds_placeholder(pre_odds_audit),
                actual_odds=actual,
                adoption_status=adoption_status,
                conclusion=conclusion,
                notes=notes,
            )
        )
    return items
