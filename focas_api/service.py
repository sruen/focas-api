"""Stable JSON service boundary for GPT Actions.

v1.2-R contract: the backend returns an evidence pack only. It does not return
any final home/draw/away tendency, recommendation, or engine-selected result.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from focas_engine.config import HARD_DATA_SOURCE
from focas_engine.io import parse_raw_input
from focas_engine.pipeline import FocasPipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TABLE_PATH = PROJECT_ROOT / HARD_DATA_SOURCE

CONTRACT_VERSION = "1.2-R"
ENGINE_VERSION = "1.2-R"

FORBIDDEN_FIELDS = [
    "final_direction",
    "recommendation",
    "home_status",
    "draw_status",
    "away_status",
    "CONFIRMED",
    "UNCONFIRMED",
]

BACKEND_RULES = [
    "后端只查表、计算、归档证据，不搜索新闻。",
    "后端不判断新闻可信度，只读取 GPT 提供的可信度标签并做降级提示。",
    "后端不输出最终方向，不输出投注建议。",
    "后端不得因即时赔率直接推翻初赔，只能输出 can_overturn_initial 布尔证据。",
    "后端不得反向改写 distribution_lock。",
]

DIRECTION_MAP = {
    "home": "home",
    "draw": "draw",
    "away": "away",
    "主胜": "home",
    "胜": "home",
    "平局": "draw",
    "平": "draw",
    "客胜": "away",
    "负": "away",
    "主胜": "home",
    "胜": "home",
    "主": "home",
    "平局": "draw",
    "平": "draw",
    "客胜": "away",
    "负": "away",
    "客": "away",
}


def _asdict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return None


def _direction_key(value: Any) -> str:
    text = str(value or "").strip()
    if text in DIRECTION_MAP:
        return DIRECTION_MAP[text]
    if "平" in text or "draw" in text.lower():
        return "draw"
    if "客" in text or "away" in text.lower():
        return "away"
    if "主" in text or "home" in text.lower():
        return "home"
    return text or "unknown"


def _position_label(status: Any) -> str:
    text = str(status or "")
    if text == "WITHIN_PSYCHOLOGICAL_INTERVAL":
        return "表内"
    if text == "LOWER_THAN_PSYCHOLOGICAL_INTERVAL":
        return "偏低"
    if text == "HIGHER_THAN_PSYCHOLOGICAL_INTERVAL":
        return "偏高"
    return "异常"


def _action_label(initial: float, current: float) -> str:
    delta = current - initial
    if delta > 0.005:
        return "升"
    if delta < -0.005:
        return "降"
    return "稳"


def _movement_size(values: list[float]) -> str:
    if not values:
        return "小"
    max_delta = max(abs(item) for item in values)
    if max_delta >= 0.35:
        return "大"
    if max_delta >= 0.12:
        return "中"
    return "小"


def _range_text(low: Any, high: Any, precision: Any = None) -> str:
    if low is None and high is None:
        return "not_available"
    if low is None or high is None:
        body = str(low if high is None else high)
    else:
        body = f"{float(low):.2f}-{float(high):.2f}"
    return f"{body}｜{precision}" if precision else body


def _company_key(company: str) -> str:
    normalized = str(company or "").strip()
    if normalized in {"威廉", "William", "william"}:
        return "William"
    if normalized in {"立博", "Ladbrokes", "ladbrokes"}:
        return "Ladbrokes"
    if normalized.lower() == "avg" or normalized == "平均欧赔":
        return "Avg"
    if normalized.lower() == "betvictor":
        return "BetVictor"
    return normalized or "Unknown"


def _information_quality_flags(raw: dict[str, Any], result: Any) -> dict[str, Any]:
    info = raw.get("information_quality") or {}
    missing = list(info.get("missing_core_info") or [])
    for item in getattr(result, "missing_fields", []) or []:
        if item not in missing:
            missing.append(item)
    low_conf = list(info.get("low_confidence_items") or [])
    downgrade = info.get("downgrade_reason") or result.stop_reason or ""
    overall = info.get("overall_rating")
    if overall not in {"A", "B", "C", "D"}:
        overall = "D" if result.stop else "C"
    return {
        "missing_core_info": missing,
        "low_confidence_items": low_conf,
        "downgrade_reason": downgrade,
        "analysis_allowed": bool(info.get("analysis_allowed", not result.stop)),
        "confidence_cap": overall,
    }


def _system_routes_by_company(result: Any) -> dict[str, dict[str, Any]]:
    expected = result.expected_opening_interval
    routes: dict[str, dict[str, Any]] = {}
    for item in result.odds_system_conversions:
        if item.snapshot_type != "initial":
            continue
        company = _company_key(item.company)
        routes[company] = {
            "refund_system": item.target_system,
            "sheet": item.target_system,
            "strength_key": getattr(expected, "p4_strength_key", None),
            "expected_low_side": _direction_key(getattr(expected, "expected_low_side", None)),
            "expected_interval_id": str(getattr(expected, "expected_interval_id", "") or ""),
            "expected_interval_min_id": getattr(expected, "expected_interval_min_id", None),
            "expected_interval_max_id": getattr(expected, "expected_interval_max_id", None),
            "expected_interval_raw_zone": getattr(expected, "expected_interval_raw_zone", None),
            "expected_interval_range_status": getattr(expected, "expected_interval_range_status", None),
            "callable_interval_ids": list(getattr(expected, "callable_interval_ids", []) or []),
            "expected_water_band": getattr(expected, "expected_water_band", None),
            "return_rate_percent": item.raw_payout_percent,
            "raw_initial_odds": [item.raw_home, item.raw_draw, item.raw_away],
        }
    return routes


def _theoretical_ranges(result: Any) -> dict[str, dict[str, str]]:
    audit = result.psychological_interval_audit
    if not audit:
        return {}
    by_system: dict[str, dict[str, str]] = {}
    for item in audit.direction_intervals:
        by_system.setdefault(item.system, {})[_direction_key(item.direction)] = _range_text(
            item.odds_min,
            item.odds_max,
            item.precision,
        )
    ranges: dict[str, dict[str, str]] = {}
    for company, route in _system_routes_by_company(result).items():
        system = route.get("sheet")
        values = by_system.get(str(system), {})
        ranges[company] = {
            "home": values.get("home", "not_available"),
            "draw": values.get("draw", "not_available"),
            "away": values.get("away", "not_available"),
        }
    return ranges


def _initial_odds_audit(result: Any) -> dict[str, dict[str, Any]]:
    audit = result.opening_board_audit
    if not audit:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for company in audit.company_audits:
        key = _company_key(company.company)
        directions = {_direction_key(item.direction): item for item in company.direction_audits}
        initial = {
            "home": directions.get("home").opening_odds if directions.get("home") else None,
            "draw": directions.get("draw").opening_odds if directions.get("draw") else None,
            "away": directions.get("away").opening_odds if directions.get("away") else None,
        }
        positions = {
            f"{name}_position": _position_label(item.position_status) if item else "异常"
            for name, item in directions.items()
        }
        low_item = min(company.direction_audits, key=lambda item: item.opening_odds, default=None)
        output[key] = {
            "initial": initial,
            "home_position": positions.get("home_position", "异常"),
            "draw_position": positions.get("draw_position", "异常"),
            "away_position": positions.get("away_position", "异常"),
            "initial_mode": "混合",
            "deviation_summary": "; ".join(
                f"{_direction_key(item.direction)}={_position_label(item.position_status)}"
                for item in company.direction_audits
            ),
            "low_side": _direction_key(low_item.direction) if low_item else None,
            "system": company.system,
            "return_rate": company.return_rate,
        }
    return output


def _raw_odds_by_company(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    odds: dict[str, dict[str, Any]] = {}
    for item in raw.get("odds", []) or []:
        company = _company_key(item.get("company", ""))
        odds[company] = item
    return odds


def _movement_pack(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_odds = _raw_odds_by_company(raw)
    pack: dict[str, dict[str, Any]] = {}
    actions_by_company: dict[str, tuple[str, str, str]] = {}
    for company, item in raw_odds.items():
        initial = item.get("initial") or {}
        current = item.get("current") or {}
        try:
            home_initial = float(initial.get("home"))
            draw_initial = float(initial.get("draw"))
            away_initial = float(initial.get("away"))
            home_current = float(current.get("home"))
            draw_current = float(current.get("draw"))
            away_current = float(current.get("away"))
        except (TypeError, ValueError):
            continue
        home_move = _action_label(home_initial, home_current)
        draw_move = _action_label(draw_initial, draw_current)
        away_move = _action_label(away_initial, away_current)
        actions_by_company[company] = (home_move, draw_move, away_move)
        path = item.get("path") or [
            {"time": "initial", "home": home_initial, "draw": draw_initial, "away": away_initial},
            {"time": "current", "home": home_current, "draw": draw_current, "away": away_current},
        ]
        pack[company] = {
            "path": [str(step) for step in path],
            "home_move": home_move,
            "draw_move": draw_move,
            "away_move": away_move,
            "movement_size": _movement_size([
                home_current - home_initial,
                draw_current - draw_initial,
                away_current - away_initial,
            ]),
            "is_reversal": len({home_move, draw_move, away_move}) > 1,
            "same_direction_with_ladbrokes": "否",
        }
    lad = actions_by_company.get("Ladbrokes")
    if lad:
        for company, actions in actions_by_company.items():
            if company == "Ladbrokes":
                pack[company]["same_direction_with_ladbrokes"] = "是"
            else:
                same = sum(1 for left, right in zip(actions, lad) if left == right)
                pack[company]["same_direction_with_ladbrokes"] = "是" if same == 3 else "否" if same == 0 else "部分"
    return pack


def _movement_authority(result: Any) -> dict[str, Any]:
    audit = result.movement_authority_audit
    if not audit:
        return {
            "can_modify_initial": False,
            "can_overturn_initial": False,
            "reason": "movement_authority_audit_not_available",
            "risk_note": "",
        }
    can_overturn = any(item.can_overturn_opening for item in audit.direction_movements)
    return {
        "can_modify_initial": bool(audit.direction_movements),
        "can_overturn_initial": can_overturn,
        "reason": audit.global_authority,
        "risk_note": "; ".join(audit.notes),
    }


def _scenario_evidence_pack(result: Any) -> dict[str, dict[str, Any]]:
    audit = result.optimal_solution_audit
    output: dict[str, dict[str, Any]] = {
        "home": {},
        "draw": {},
        "away": {},
    }
    if not audit:
        return output
    for scenario in audit.scenarios:
        key = _direction_key(scenario.target_direction)
        output[key] = {
            "supporting_facts": list(scenario.evidence),
            "counter_facts": list(scenario.contradictions),
            "odds_structure_fit": scenario.opening_fit,
            "movement_fit": scenario.movement_fit,
            "narrative_usage": ", ".join(scenario.required_topic_usage),
            "explanation_cost_hint": "低" if scenario.explanation_score >= 0.72 else "中" if scenario.explanation_score >= 0.55 else "高",
            "explanation_score": scenario.explanation_score,
        }
    return output


def analyze_match_input(
    match_input: dict[str, Any],
    *,
    table_path: str | Path | None = None,
    include_report: bool = False,
) -> dict[str, Any]:
    """Run FOCAS and return the v1.2-R evidence boundary consumed by a GPT Action."""

    loaded = parse_raw_input(match_input)
    match, strength, pulls, book_mode, odds = loaded.as_tuple()
    result = FocasPipeline(table_path=str(table_path or DEFAULT_TABLE_PATH)).run(
        match=match,
        strength=strength,
        pulls=pulls,
        narrative_materials=loaded.narrative_materials,
        book_mode=book_mode,
        odds=odds,
    )

    payload: dict[str, Any] = {
        "api_schema_version": CONTRACT_VERSION,
        "engine_version": ENGINE_VERSION,
        "backend_scope": "evidence_only_no_final_direction",
        "forbidden_fields": list(FORBIDDEN_FIELDS),
        "backend_rules": list(BACKEND_RULES),
        "status": {
            "stop": result.stop,
            "stop_node": result.stop_node,
            "stop_reason": result.stop_reason,
            "report_mode": result.report_mode,
            "evidence_status": result.decision_status,
            "backend_tendency_allowed": False,
            "odds_analysis_status": result.odds_analysis_status,
            "table_read_confirmed": result.table_read_confirmed,
            "skeleton_scope_status": result.skeleton_scope_status,
        },
        "match": {
            "home_team": match.home_team,
            "away_team": match.away_team,
            "competition": match.competition,
            "kickoff_time": match.kickoff_time,
            "stage": match.stage,
            "neutral_venue": match.neutral_venue,
            "real_home_away": match.real_home_away,
            "result_scope": match.result_scope or match.extra_time_or_penalties,
            "extra_time_or_penalties": match.extra_time_or_penalties,
        },
        "information_quality_flags": _information_quality_flags(loaded.raw, result),
        "source_reliability_echo": loaded.raw.get("source_reliability") or {},
        "distribution_lock_echo": loaded.raw.get("distribution_lock") or {},
        "skeleton_route": _system_routes_by_company(result),
        "theoretical_ranges": _theoretical_ranges(result),
        "initial_odds_audit": _initial_odds_audit(result),
        "movement_pack": _movement_pack(loaded.raw),
        "movement_authority_audit": _movement_authority(result),
        "scenario_evidence_pack": _scenario_evidence_pack(result),
        "evidence_appendix": {
            "expected_opening_interval": _asdict(result.expected_opening_interval),
            "fundamental_topic_audit": _asdict(result.fundamental_topic_audit),
            "market_pull_audit": _asdict(result.market_pull_audit),
            "opening_anchor_audit": _asdict(result.opening_anchor_audit),
            "bookmaker_topic_usage_audit": _asdict(result.bookmaker_topic_usage_audit),
            "psychological_interval_audit": _asdict(result.psychological_interval_audit),
            "opening_board_audit": _asdict(result.opening_board_audit),
            "notes": list(result.notes),
        },
    }
    if include_report:
        payload["report_markdown"] = (
            "v1.2-R 后端只返回 evidence pack，不生成最终赛果方向报告。"
            "请由 GPT 根据 evidence pack 独立撰写分析。"
        )
    return payload
