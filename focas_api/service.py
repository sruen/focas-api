"""Stable JSON service boundary for GPT Actions."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from focas_engine.config import HARD_DATA_SOURCE
from focas_engine.io import parse_raw_input
from focas_engine.pipeline import FocasPipeline
from focas_engine.report import render_frontend_report

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TABLE_PATH = PROJECT_ROOT / HARD_DATA_SOURCE


def _system_routes(result: Any) -> list[dict[str, Any]]:
    return [
        {
            "company": item.company,
            "snapshot_type": item.snapshot_type,
            "raw_odds": [item.raw_home, item.raw_draw, item.raw_away],
            "return_rate_percent": item.raw_payout_percent,
            "detected_system": item.detected_system,
            "target_sheet_system": item.target_system,
            "system_distance": item.system_distance,
            "system_lookup_status": item.system_lookup_status,
            "numerical_conversion_applied": item.numerical_conversion_applied,
            "routing_mode": item.system_routing_mode,
        }
        for item in result.odds_system_conversions
    ]


def _opening_audits(result: Any) -> list[dict[str, Any]]:
    interval_audit = result.interval_audit
    return [asdict(item) for item in interval_audit.audits] if interval_audit else []


def _opening_motives(result: Any) -> list[dict[str, Any]]:
    stage = result.stage_9_analysis
    return [asdict(item) for item in getattr(stage, "opening_motive_chain", [])] if stage else []


def _validate_recent_matches(match_input: dict[str, Any]) -> None:
    """Reject recent-form inputs that the engine cannot parse reliably.

    OpenAPI already documents the W/D/L prefix convention. This service-level
    validation makes that convention enforceable for GPT Actions and package
    loaders, preventing score strings such as "2026-05-31 A 0-2 B" from being
    parsed from the wrong team perspective.
    """

    for side in ("home_context", "away_context"):
        context = match_input.get(side) or {}
        matches = context.get("recent_matches") or []
        if len(matches) < 5:
            raise ValueError(f"{side}.recent_matches must contain at least 5 W/D/L-prefixed records")
        bad = [
            item
            for item in matches
            if not isinstance(item, str) or not item.strip().upper().startswith(("W ", "D ", "L "))
        ]
        if bad:
            raise ValueError(
                f"{side}.recent_matches items must start with 'W ', 'D ', or 'L '. "
                f"Bad examples: {bad[:2]}"
            )


def _direction_actions(opening_board_audit: dict[str, Any] | None) -> dict[str, list[str]]:
    actions: dict[str, list[str]] = {"主胜": [], "平局": [], "客胜": []}
    if not opening_board_audit:
        return actions
    for company in opening_board_audit.get("company_audits", []) or []:
        for item in company.get("direction_audits", []) or []:
            direction = item.get("direction")
            action = item.get("action")
            if direction in actions and action:
                actions[direction].append(action)
    return actions


def _movement_contradiction_audit(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose pull-vs-movement contradictions so GPT cannot skip them."""

    pull_audit = payload.get("market_pull_audit") or {}
    directions = {
        item.get("direction"): item
        for item in pull_audit.get("directions", []) or []
        if isinstance(item, dict)
    }
    actions = _direction_actions(payload.get("opening_board_audit"))

    def pull_percent(direction: str) -> float:
        try:
            return float((directions.get(direction) or {}).get("pull_percent") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def pull_label(direction: str) -> str:
        return str((directions.get(direction) or {}).get("pull_label") or "")

    def is_strong(direction: str) -> bool:
        return pull_label(direction) == "强" or pull_percent(direction) >= 35.0

    def count(direction: str, action: str) -> int:
        return actions.get(direction, []).count(action)

    out: list[dict[str, Any]] = []

    if is_strong("客胜") and count("客胜", "抬高") >= 2:
        out.append(
            {
                "target_direction": "主胜",
                "contradiction_type": "dispersion_side_weakened",
                "severity": "HIGH",
                "message": "客胜原始拉力强，但后市客赔被多家公司抬高，客胜分流能力被削弱；若主胜为目标，需说明主胜暴露风险。",
                "must_explain_before_final": True,
            }
        )

    if is_strong("主胜") and count("主胜", "拉低") >= 2 and count("平局", "拉低") >= 2:
        out.append(
            {
                "target_direction": "平局",
                "contradiction_type": "left_lean_board",
                "severity": "MEDIUM",
                "message": "主胜与平局同步拉低，赔面左倾；平局可能具备隐蔽性，但必须检查客胜是否仍能承担胜负分流。",
                "must_explain_before_final": True,
            }
        )

    if is_strong("客胜") and count("客胜", "抬高") >= 2:
        out.append(
            {
                "target_direction": "客胜",
                "contradiction_type": "target_odds_raised_after_public_pull",
                "severity": "MEDIUM",
                "message": "客胜有强拉力却被后市抬高，需要区分保护、阻挡、降热或放弃，不能机械解释为客胜保护。",
                "must_explain_before_final": True,
            }
        )

    return out


def _gpt_execution_gate(payload: dict[str, Any]) -> dict[str, Any]:
    optimal = payload.get("optimal_solution_audit") or {}
    final = payload.get("final_structure_judgement") or {}
    status_payload = payload.get("status") or {}
    status = optimal.get("solution_status") or final.get("status") or status_payload.get("decision_status")
    scenarios = optimal.get("scenarios") or []
    scenario_directions = [
        item.get("target_direction")
        for item in scenarios
        if isinstance(item, dict) and item.get("target_direction")
    ]
    required_audits = [
        "fundamental_topic_audit",
        "strength_dynamic_audit",
        "original_distribution_audit",
        "market_pull_audit",
        "skeleton_system_audit",
        "psychological_interval_audit",
        "opening_board_audit",
        "pre_odds_predicted_odds_audit",
        "three_direction_development_matrix",
        "bookmaker_topic_usage_audit",
        "optimal_solution_audit",
        "future_adjustment_plan",
        "final_structure_judgement",
    ]
    missing_audits = [key for key in required_audits if not payload.get(key)]
    stop = bool(status_payload.get("stop"))
    all_three_scenarios_present = {"主胜", "平局", "客胜"}.issubset(set(scenario_directions))
    final_output_allowed = (not stop) and not missing_audits and all_three_scenarios_present

    return {
        "stop": stop,
        "stop_node": status_payload.get("stop_node"),
        "stop_reason": status_payload.get("stop_reason"),
        "final_output_allowed": final_output_allowed,
        "missing_audits": missing_audits,
        "scenario_directions_present": scenario_directions,
        "all_three_scenarios_present": all_three_scenarios_present,
        "read_order": [
            "fundamental_topic_audit",
            "strength_dynamic_audit",
            "original_distribution_audit",
            "market_pull_audit",
            "skeleton_system_audit",
            "psychological_interval_audit",
            "opening_board_audit",
            "pre_odds_predicted_odds_audit",
            "three_direction_development_matrix",
            "bookmaker_topic_usage_audit",
            "optimal_solution_audit.scenarios",
            "movement_contradiction_audit",
            "future_adjustment_plan",
            "final_structure_judgement",
        ],
        "final_direction_policy": "READ_LAST_ONLY",
        "all_three_scenarios_required": True,
        "must_explain_before_final": [
            "six_fundamental_topic_categories",
            "strength_dynamic_audit",
            "original_distribution_type",
            "three_direction_market_pull",
            "three_direction_opening_position",
            "three_direction_movement",
            "pre_odds_predicted_odds_formula_gate",
            "three_direction_development_matrix",
            "bookmaker_topic_usage_by_direction",
            "home_draw_away_optimal_solution_scenarios",
            "movement_vs_pull_contradictions",
        ],
        "better_solution_only": status == "BETTER_SOLUTION_ONLY",
        "better_solution_policy": (
            "If solution_status or final status is BETTER_SOLUTION_ONLY, GPT must say it is not a clean optimal solution, "
            "only the highest-explanation relative solution, and must explain contradictions before final judgement."
        ),
        "forbidden_shortcuts": [
            "Do not use final_structure_judgement.direction as the answer outline.",
            "Do not describe BETTER_SOLUTION_ONLY as a clean optimal solution.",
            "Do not explain odds movement before explaining available fundamental topics.",
            "Do not skip draw and away scenarios when selected_direction is home.",
            "Do not call an opening price '拉低' or '抬高'; only movement can be described that way.",
            "Do not invent broad-strength grades; use strength_dynamic_audit only.",
            "Do not invent exact predicted development odds when formula gate is not confirmed.",
            "Do not skip original_distribution_audit.distribution_type.",
            "Do not write only pull percentages without distribution type.",
        ],
        "exact_predicted_odds_allowed": bool(
            (payload.get("pre_odds_predicted_odds_audit") or {}).get("gpt_may_generate_exact_odds") is True
        ),
        "movement_contradiction_count": len(payload.get("movement_contradiction_audit") or []),
    }


def analyze_match_input(
    match_input: dict[str, Any],
    *,
    table_path: str | Path | None = None,
    include_report: bool = False,
) -> dict[str, Any]:
    """Run FOCAS and return the evidence boundary consumed by a GPT Action."""

    _validate_recent_matches(match_input)
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
    interval_audit = result.interval_audit
    payload: dict[str, Any] = {
        "api_schema_version": "1.0",
        "engine_version": "1.1.5",
        "analysis_contract": {
            "odds_numerical_conversion_allowed": False,
            "odds_comparison_basis": "raw_institution_odds",
            "return_rate_usage": "route_to_matching_89_96_system_sheet_only",
            "institution_motive_requires_confirmed_skeleton_audit": True,
            "analysis_mode": "FINAL_PASS_GATE_DISABLED",
            "lean_output_allowed": True,
            "final_structure_judgement_policy": "READ_LAST_AFTER_REQUIRED_AUDITS",
            "legacy_pass_gate_replaced_by_optimal_solution_layer": True,
            "optimal_solution_layer_enabled": True,
            "market_pull_percent_means": "market_psychological_pull_share_not_match_probability",
            "three_direction_board_audit_enabled": True,
        },
        "match": {
            "home_team": match.home_team,
            "away_team": match.away_team,
            "competition": match.competition,
            "kickoff_time": match.kickoff_time,
        },
        "status": {
            "stop": result.stop,
            "stop_node": result.stop_node,
            "stop_reason": result.stop_reason,
            "report_mode": result.report_mode,
            "decision_status": result.decision_status,
            "mainline_output_status": result.mainline_output_status,
            "odds_analysis_status": result.odds_analysis_status,
            "final_direction": result.final_direction,
            "structural_lean": result.structural_lean,
            "strength_source": result.strength_source,
            "table_read_confirmed": result.table_read_confirmed,
            "expected_interval_status": result.expected_interval_status,
            "skeleton_scope_status": result.skeleton_scope_status,
        },
        "expected_opening_interval": asdict(result.expected_opening_interval)
        if result.expected_opening_interval
        else None,
        "strength_dynamic_audit": asdict(result.strength_dynamic_audit)
        if result.strength_dynamic_audit
        else None,
        "original_distribution_audit": asdict(result.original_distribution_audit)
        if result.original_distribution_audit
        else None,
        "system_routes": _system_routes(result),
        "skeleton_system_audit": _system_routes(result),
        "opening_skeleton_audits": _opening_audits(result),
        "psychological_interval_audit": asdict(result.psychological_interval_audit)
        if result.psychological_interval_audit
        else None,
        "opening_board_audit": asdict(result.opening_board_audit)
        if result.opening_board_audit
        else None,
        "pre_odds_predicted_odds_audit": asdict(result.pre_odds_predicted_odds_audit)
        if result.pre_odds_predicted_odds_audit
        else None,
        "three_direction_development_matrix": [
            asdict(item) for item in result.three_direction_development_matrix
        ],
        "fundamental_topic_audit": asdict(result.fundamental_topic_audit)
        if result.fundamental_topic_audit
        else None,
        "market_pull_audit": asdict(result.market_pull_audit)
        if result.market_pull_audit
        else None,
        "optimal_solution_audit": asdict(result.optimal_solution_audit)
        if result.optimal_solution_audit
        else None,
        "bookmaker_topic_usage_audit": asdict(result.bookmaker_topic_usage_audit)
        if result.bookmaker_topic_usage_audit
        else None,
        "future_adjustment_plan": asdict(result.future_adjustment_plan)
        if result.future_adjustment_plan
        else None,
        "final_structure_judgement": asdict(result.final_structure_judgement)
        if result.final_structure_judgement
        else None,
        "opening_motive_chain": _opening_motives(result),
        "narrative_audit": asdict(result.narrative_audit) if result.narrative_audit else None,
        "scenario_audit": asdict(result.scenario_audit) if result.scenario_audit else None,
        "notes": list(result.notes),
    }
    if interval_audit:
        payload["opening_interval_audit"] = {
            "ok": interval_audit.ok,
            "stop_reason": interval_audit.stop_reason,
            "notes": list(interval_audit.notes),
        }

    payload["movement_contradiction_audit"] = _movement_contradiction_audit(payload)
    payload["gpt_execution_gate"] = _gpt_execution_gate(payload)

    preferred_order = [
        "api_schema_version",
        "engine_version",
        "analysis_contract",
        "gpt_execution_gate",
        "movement_contradiction_audit",
        "match",
        "status",
        "expected_opening_interval",
        "strength_dynamic_audit",
        "fundamental_topic_audit",
        "original_distribution_audit",
        "market_pull_audit",
        "system_routes",
        "skeleton_system_audit",
        "opening_skeleton_audits",
        "psychological_interval_audit",
        "opening_board_audit",
        "pre_odds_predicted_odds_audit",
        "three_direction_development_matrix",
        "optimal_solution_audit",
        "bookmaker_topic_usage_audit",
        "future_adjustment_plan",
        "final_structure_judgement",
        "opening_motive_chain",
        "narrative_audit",
        "scenario_audit",
        "opening_interval_audit",
        "notes",
    ]
    payload = {
        **{key: payload[key] for key in preferred_order if key in payload},
        **{key: value for key, value in payload.items() if key not in preferred_order},
    }

    if include_report:
        payload["report_markdown"] = render_frontend_report(
            match=match,
            strength=strength,
            pulls=pulls,
            book_mode=book_mode,
            odds=odds,
            result=result,
        )
    return payload
