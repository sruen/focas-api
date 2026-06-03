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
    """Material-only gate for GPT.

    This gate deliberately does not authorize a backend final direction. It only
    tells GPT whether the material package is usable for independent V3.9.1/V4
    reasoning.
    """

    status_payload = payload.get("status") or {}
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
    ]
    missing_audits = [key for key in required_audits if not payload.get(key)]
    stop = bool(status_payload.get("stop"))
    material_audit_allowed = (not stop) and not missing_audits

    return {
        "stop": stop,
        "stop_node": status_payload.get("stop_node"),
        "stop_reason": status_payload.get("stop_reason"),
        "material_audit_allowed": material_audit_allowed,
        "final_output_allowed": False,
        "final_direction_policy": "GPT_INDEPENDENT_JUDGEMENT_REQUIRED",
        "backend_final_policy": "REFERENCE_ONLY_NOT_AN_ANSWER_ANCHOR",
        "missing_audits": missing_audits,
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
            "movement_contradiction_audit",
            "backend_reference_judgement",
        ],
        "must_complete_before_judgement": [
            "basic_context_and_fundamental_first_eye",
            "theoretical_development_position_or_predicted_opening_interval",
            "actual_opening_position_comparison",
            "William_and_Ladbrokes_opening_anchor",
            "movement_permission_audit",
            "three_result_optimal_solution_reasoning_by_GPT",
            "reverse_audit_cost_ranking_by_GPT",
            "five_counter_questions_by_GPT",
            "one_paragraph_bookmaker_mainline_summary",
        ],
        "forbidden_shortcuts": [
            "Do not use backend_reference_judgement as the answer outline.",
            "Do not treat BETTER_SOLUTION_ONLY or reference_lean as final direction.",
            "Do not skip independent three-result optimal-solution reasoning.",
            "Do not call an opening price '拉低' or '抬高'; only movement can be described that way.",
            "Do not invent broad-strength grades; use strength_dynamic_audit or user-provided match context only.",
            "Do not invent exact predicted development odds when formula gate is not confirmed.",
            "Do not write only tables; final judgement must include a bookmaker mainline paragraph.",
        ],
        "exact_predicted_odds_allowed": bool(
            (payload.get("pre_odds_predicted_odds_audit") or {}).get("gpt_may_generate_exact_odds") is True
        ),
        "movement_contradiction_count": len(payload.get("movement_contradiction_audit") or []),
    }


def _scrub_directional_keys(value: Any) -> Any:
    """Remove backend-selected directions so the API cannot anchor GPT."""

    if isinstance(value, dict):
        blocked = {"direction", "selected_direction", "final_direction", "structural_lean"}
        return {
            key: _scrub_directional_keys(item)
            for key, item in value.items()
            if key not in blocked
        }
    if isinstance(value, list):
        return [_scrub_directional_keys(item) for item in value]
    return value


def _backend_reference(result: Any) -> dict[str, Any]:
    return {
        "reference_only": True,
        "policy": "Backend judgement is intentionally scrubbed and may not anchor GPT. GPT must independently apply V3.9.1 initial-anchor, movement-permission, reverse-audit and counter-question logic.",
        "decision_status": result.decision_status,
        "mainline_output_status": result.mainline_output_status,
        "reference_lean_present": bool(getattr(result, "structural_lean", None)),
        "final_judgement_present": bool(getattr(result, "final_structure_judgement", None)),
        "scrubbed_final_structure_judgement": _scrub_directional_keys(
            asdict(result.final_structure_judgement) if result.final_structure_judgement else None
        ),
    }


def _scrub_optimal_solution(optimal: Any) -> dict[str, Any] | None:
    if optimal is None:
        return None
    data = asdict(optimal)
    if "selected_direction" in data:
        data["reference_selected_direction_removed"] = True
        data.pop("selected_direction", None)
    return data


def _build_material_payload(result: Any, loaded: Any, include_report: bool) -> dict[str, Any]:
    match, strength, pulls, book_mode, odds = loaded.as_tuple()
    interval_audit = result.interval_audit
    payload: dict[str, Any] = {
        "api_schema_version": "1.1-material",
        "engine_version": "1.1.5-material-audit",
        "analysis_contract": {
            "core_instruction_version": "FOCASGPT_CORE_INSTRUCTIONS_v1.0",
            "judgement_layer": "PROJECT_SOURCES_V3.9.1_PLUS_V4",
            "backend_role": "MATERIAL_AUDIT_AND_CONFLICT_CHECK_ONLY",
            "odds_numerical_conversion_allowed": False,
            "odds_comparison_basis": "raw_institution_odds",
            "return_rate_usage": "route_to_matching_89_96_system_sheet_only",
            "analysis_mode": "MATERIAL_AUDIT_ONLY",
            "lean_output_allowed": False,
            "backend_final_is_reference_only": True,
            "final_structure_judgement_removed_from_primary_payload": True,
            "gpt_independent_judgement_required": True,
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
            "odds_analysis_status": result.odds_analysis_status,
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
        "scenario_simulation_reference": _scrub_optimal_solution(result.optimal_solution_audit),
        "bookmaker_topic_usage_audit": asdict(result.bookmaker_topic_usage_audit)
        if result.bookmaker_topic_usage_audit
        else None,
        "future_adjustment_reference": asdict(result.future_adjustment_plan)
        if result.future_adjustment_plan
        else None,
        "backend_reference_judgement": _backend_reference(result),
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
        "scenario_simulation_reference",
        "bookmaker_topic_usage_audit",
        "future_adjustment_reference",
        "backend_reference_judgement",
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


def audit_match_input(
    match_input: dict[str, Any],
    *,
    table_path: str | Path | None = None,
    include_report: bool = False,
) -> dict[str, Any]:
    """Run FOCAS as a material-audit boundary consumed by GPT Actions."""

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
    return _build_material_payload(result, loaded, include_report=include_report)


def analyze_match_input(
    match_input: dict[str, Any],
    *,
    table_path: str | Path | None = None,
    include_report: bool = False,
) -> dict[str, Any]:
    """Backward-compatible alias. Returns material audit, not final judgement."""

    return audit_match_input(match_input, table_path=table_path, include_report=include_report)


def _matrix_item(audit_payload: dict[str, Any], direction: str) -> dict[str, Any] | None:
    for item in audit_payload.get("three_direction_development_matrix") or []:
        if isinstance(item, dict) and item.get("target_direction") == direction:
            return item
    return None


def _severity_rank(severity: str) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "HARD_STOP": 4}.get(severity, 0)


def verify_independent_judgement(
    *,
    audit_payload: dict[str, Any],
    independent_judgement: dict[str, Any],
) -> dict[str, Any]:
    """Validate GPT's independent judgement without selecting a new direction."""

    direction = independent_judgement.get("selected_direction") or independent_judgement.get("direction")
    requested_grade = independent_judgement.get("structure_grade") or independent_judgement.get("grade")
    excluded = independent_judgement.get("excluded_directions") or []
    conflicts: list[dict[str, Any]] = []
    hard_vetoes: list[dict[str, Any]] = []

    if direction not in {"主胜", "平局", "客胜", "胜", "平", "负", "PASS", "胜+平", "平+负"}:
        conflicts.append({
            "type": "missing_or_invalid_direction",
            "severity": "HARD_STOP",
            "message": "independent_judgement.selected_direction must be 主胜/平局/客胜/胜/平/负/胜+平/平+负/PASS.",
            "action": "REJECT",
        })

    normalized = {"胜": "主胜", "平": "平局", "负": "客胜"}.get(direction, direction)
    item = _matrix_item(audit_payload, normalized) if normalized in {"主胜", "平局", "客胜"} else None
    matrix_alignment = "NOT_APPLICABLE"
    max_allowed_grade = "B"

    if item:
        adoption = str(item.get("adoption_status") or "UNCONFIRMED")
        if adoption == "ADOPTED":
            matrix_alignment = "MATCH"
            max_allowed_grade = "A" if len(excluded) >= 2 else "B"
        elif adoption in {"PARTIAL_ADOPTED", "STRONG_PARTIAL"}:
            matrix_alignment = "PARTIAL_MATCH"
            max_allowed_grade = "B"
        elif adoption in {"NOT_ADOPTED", "UNCONFIRMED", "OVER_RAISED_REVIEW", "PARTIAL_OR_OVER_RAISED"}:
            matrix_alignment = "MISMATCH"
            conflicts.append({
                "type": "matrix_not_supporting_selected_direction",
                "severity": "HIGH" if adoption != "NOT_ADOPTED" else "HARD_STOP",
                "target_direction": normalized,
                "message": f"three_direction_development_matrix shows adoption_status={adoption}; GPT cannot output this as a strong final structure.",
                "action": "REJECT" if adoption == "NOT_ADOPTED" else "DOWNGRADE_OR_REVIEW",
            })
            max_allowed_grade = "C"
    elif normalized in {"主胜", "平局", "客胜"}:
        matrix_alignment = "MISSING"
        conflicts.append({
            "type": "matrix_item_missing",
            "severity": "HIGH",
            "target_direction": normalized,
            "message": "No three_direction_development_matrix item found for selected direction.",
            "action": "REVIEW_REQUIRED",
        })
        max_allowed_grade = "C"

    strength_audit = audit_payload.get("strength_dynamic_audit") or {}
    if strength_audit and strength_audit.get("ok") is False:
        conflicts.append({
            "type": "strength_grade_unconfirmed",
            "severity": "HIGH",
            "message": "strength_dynamic_audit is not OK; GPT may not give a strong structure.",
            "action": "DOWNGRADE",
        })
        max_allowed_grade = "C"

    gate = audit_payload.get("gpt_execution_gate") or {}
    if gate.get("material_audit_allowed") is False:
        conflicts.append({
            "type": "material_audit_not_allowed",
            "severity": "HARD_STOP",
            "message": "Material audit gate did not allow independent final output; missing audits or stop state exists.",
            "action": "REJECT",
        })

    for contradiction in audit_payload.get("movement_contradiction_audit") or []:
        if not isinstance(contradiction, dict):
            continue
        target = contradiction.get("target_direction")
        severity = contradiction.get("severity", "")
        if target == normalized or _severity_rank(str(severity)) >= 3:
            conflicts.append({
                "type": "movement_contradiction_unresolved",
                "severity": severity or "MEDIUM",
                "target_direction": target,
                "message": contradiction.get("message") or "Movement contradiction must be explained before output.",
                "action": "REVIEW_REQUIRED" if severity != "HIGH" else "DOWNGRADE_OR_REVIEW",
            })

    # Optional explicit hard vetoes supplied by GPT or future API layers.
    for veto in independent_judgement.get("hard_vetoes") or []:
        if isinstance(veto, dict) and veto.get("resolved") is False:
            hard_vetoes.append(veto)
            conflicts.append({
                "type": "hard_veto_unresolved",
                "severity": "HARD_STOP",
                "message": veto.get("message") or "Unresolved hard veto.",
                "action": "REJECT",
            })

    # Grade overreach guard.
    grade_order = {"PASS": 0, "C": 1, "B": 2, "B+": 2, "A": 3, "A+": 3, "S": 4}
    if requested_grade and grade_order.get(str(requested_grade), 0) > grade_order.get(max_allowed_grade, 0):
        conflicts.append({
            "type": "grade_exceeds_allowed_level",
            "severity": "MEDIUM",
            "message": f"Requested grade {requested_grade} exceeds max_allowed_grade {max_allowed_grade}.",
            "action": "DOWNGRADE",
        })

    hard_stop = any(_severity_rank(str(item.get("severity", ""))) >= 4 for item in conflicts)
    high_conflict = any(_severity_rank(str(item.get("severity", ""))) >= 3 for item in conflicts)
    if hard_stop:
        verification_status = "REJECT"
        direction_allowed = False
        final_output_allowed = False
    elif high_conflict:
        verification_status = "REVIEW_REQUIRED"
        direction_allowed = True
        final_output_allowed = False
    elif conflicts:
        verification_status = "DOWNGRADED"
        direction_allowed = True
        final_output_allowed = True
    else:
        verification_status = "PASS_CHECKED"
        direction_allowed = True
        final_output_allowed = True

    return {
        "api_schema_version": "1.1-verification",
        "verification_contract": {
            "backend_role": "VERIFY_GPT_JUDGEMENT_ONLY",
            "does_not_select_new_direction": True,
            "does_not_override_gpt_reasoning": True,
        },
        "verification_status": verification_status,
        "gpt_selected_direction": direction,
        "direction_allowed": direction_allowed,
        "final_output_allowed": final_output_allowed,
        "max_allowed_grade": max_allowed_grade,
        "matrix_alignment": matrix_alignment,
        "two_direction_exclusion": len(excluded) >= 2,
        "conflicts": conflicts,
        "hard_vetoes": hard_vetoes,
        "required_rewrite_points": [item.get("message") for item in conflicts if item.get("message")],
    }
