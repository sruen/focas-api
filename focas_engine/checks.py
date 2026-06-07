from __future__ import annotations

from .models import (
    CompanyOdds,
    GateResult,
    MatchContext,
    NaturalPull,
    OddsSystemConversion,
    OriginalBookMode,
    OriginalDistribution,
    StrengthContext,
)
from .odds_system import require_hard_company_conversions
from .placeholder_detector import is_placeholder_text, invalid_list_items
from .strength import ALLOWED_GRADES


MATCH_REQUIRED = {
    "home_team": "主队名称",
    "away_team": "客队名称",
    "competition": "赛事名称",
    "kickoff_time": "比赛时间",
    "stage": "比赛阶段",
    "neutral_venue": "是否中立场",
    "single_leg": "是否单回合",
    "match_type": "赛事类型",
    "extra_time_or_penalties": "加时/点球规则",
    "real_home_away": "主客属性是否真实存在",
    "attention_level": "赛事关注度/受注关注度",
}

TEAM_REQUIRED = {
    "name": "队伍名称",
    "rank": "排名",
    "points": "积分",
    "recent_matches": "近5-6场",
    "venue_adaptation": "主场/客场/中立场适应",
    "attack_state": "进攻状态",
    "defense_state": "防守状态",
    "injuries": "伤停/复出/阵容完整度",
    "schedule_fatigue": "赛程体能",
    "motivation": "战意",
    "popularity_story": "人气/名气/冠军叙事",
    "major_recent_matches": "近期重大比赛表现",
}

H2H_REQUIRED = {
    "overall": "总体交锋",
    "recent_years": "近年交锋",
    "same_competition": "同赛事交锋",
    "venue_specific": "主客/中立场交锋",
    "latest_key_match": "最近一次关键交锋",
    "market_psychology": "往绩对市场心理影响",
}

STRENGTH_REQUIRED = {
    "home_grade": "主队广义实力档位",
    "away_grade": "客队广义实力档位",
    "static_gap": "静态档位差",
    "dynamic_adjustment": "动态修正",
    "final_gap": "最终广义实力差",
}

BOOK_MODE_REQUIRED = {
    "mode": "原书模式",
    "reason": "挂接原因",
    "key_odds_to_watch": "最需要观察的赔率项",
    "easiest_misread": "最容易误读的位置",
}


def _empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return is_placeholder_text(value)
    if isinstance(value, list):
        if len(value) < 5:
            return True
        return bool(invalid_list_items(value))
    return False


def basic_context_gate(ctx: MatchContext) -> GateResult:
    missing: list[str] = []
    for attr, label in MATCH_REQUIRED.items():
        if _empty(getattr(ctx, attr)):
            missing.append(label)

    for side_name, team in (("主队", ctx.home), ("客队", ctx.away)):
        if team is None:
            missing.append(f"{side_name}基本面整体")
            continue
        for attr, label in TEAM_REQUIRED.items():
            if _empty(getattr(team, attr)):
                missing.append(f"{side_name}{label}")

    if ctx.h2h is None:
        missing.append("往绩整体")
    else:
        for attr, label in H2H_REQUIRED.items():
            if _empty(getattr(ctx.h2h, attr)):
                missing.append(label)

    return GateResult(
        name="基本面硬闸门",
        ok=not missing,
        missing=missing,
        reason="基本面不完整，不得进入赔率结论。",
    )


def strength_gate(strength: StrengthContext) -> GateResult:
    missing = [label for attr, label in STRENGTH_REQUIRED.items() if _empty(getattr(strength, attr))]
    if strength.home_grade and strength.home_grade not in ALLOWED_GRADES:
        missing.append(f"主队广义实力档位非法：{strength.home_grade}")
    if strength.away_grade and strength.away_grade not in ALLOWED_GRADES:
        missing.append(f"客队广义实力档位非法：{strength.away_grade}")
    return GateResult(
        name="广义实力分档闸门",
        ok=not missing,
        missing=missing,
        reason="没有广义实力档位与档位差，不能确定心理区间。",
    )


def natural_pull_gate(pulls: list[NaturalPull]) -> GateResult:
    by_dir = {p.direction: p for p in pulls}
    missing: list[str] = []
    for direction in ("主胜", "平局", "客胜"):
        p = by_dir.get(direction)
        if p is None:
            missing.append(f"{direction}自然拉力整体")
            continue
        if _empty(p.strength):
            missing.append(f"{direction}强弱")
        if _empty(p.facts):
            missing.append(f"{direction}事实依据")
        if _empty(p.market_psychology):
            missing.append(f"{direction}市场心理")
        if _empty(p.popularity_direction):
            missing.append(f"{direction}人气方向")
        if p.easy_to_receive is None:
            missing.append(f"{direction}是否容易受注")
        if p.first_eye_direction is None:
            missing.append(f"{direction}是否大众第一眼方向")
    return GateResult(
        name="三项自然拉力闸门",
        ok=not missing,
        missing=missing,
        reason="没有三项自然拉力，不能判断赔率动作的分布改造对象。",
    )


def original_distribution_gate(distribution: OriginalDistribution | None) -> GateResult:
    missing: list[str] = []
    if distribution is None:
        missing.append("原始分布整体")
    else:
        for attr, label in (
            ("distribution_type", "原始分布类型"),
            ("home_pressure", "主胜原始压力"),
            ("draw_pressure", "平局原始压力"),
            ("away_pressure", "客胜原始压力"),
            ("confidence_sources", "信心来源"),
            ("dispersion_available", "可分流方向"),
            ("reasoning", "判断理由"),
        ):
            if not getattr(distribution, attr):
                missing.append(label)
    return GateResult(
        name="原始分布闸门",
        ok=not missing,
        missing=missing,
        reason="原始分布必须在赔率分析前完成，且不能由赔率倒推。",
    )


def original_book_mode_gate(mode: OriginalBookMode) -> GateResult:
    missing = [label for attr, label in BOOK_MODE_REQUIRED.items() if _empty(getattr(mode, attr))]
    return GateResult(
        name="原书模式挂接闸门",
        ok=not missing,
        missing=missing,
        reason="没有原书模式挂接，不能进入公司做盘解释。",
    )


def odds_gate(odds: list[CompanyOdds]) -> GateResult:
    companies = {str(o.company).lower() for o in odds}
    missing: list[str] = []
    if not any(c in {"william", "威廉"} for c in companies):
        missing.append("William赔率")
    if not any(c in {"ladbrokes", "立博"} for c in companies):
        missing.append("Ladbrokes赔率")
    if not odds:
        missing.append("赔率整体")
    return GateResult(
        name="赔率输入闸门",
        ok=not missing,
        missing=missing,
        reason="缺少 William / Ladbrokes 核心赔率，不得比较公司做盘。Avg 缺失只作为信息质量降级，不阻断后端 evidence pack。",
    )


def odds_system_routing_gate(conversions: list[OddsSystemConversion]) -> GateResult:
    ok, missing = require_hard_company_conversions(conversions)
    return GateResult(
        name="赔率体系识别与骨架表路由闸门",
        ok=ok,
        missing=missing,
        reason="William / Ladbrokes 必须先完成初赔与即时赔返还率体系识别，才能按对应骨架表查表。赔率数值不做二次转换。",
    )


def odds_system_conversion_gate(conversions: list[OddsSystemConversion]) -> GateResult:
    """Backward-compatible alias for the return-rate system routing gate."""
    return odds_system_routing_gate(conversions)
