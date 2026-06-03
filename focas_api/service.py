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


def analyze_match_input(
    match_input: dict[str, Any],
    *,
    table_path: str | Path | None = None,
    include_report: bool = False,
) -> dict[str, Any]:
    """Run FOCAS and return the evidence boundary consumed by a GPT Action."""

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
            "pass_must_not_be_overridden_by_gpt": True,
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
            "table_read_confirmed": result.table_read_confirmed,
            "expected_interval_status": result.expected_interval_status,
            "skeleton_scope_status": result.skeleton_scope_status,
        },
        "expected_opening_interval": asdict(result.expected_opening_interval)
        if result.expected_opening_interval
        else None,
        "system_routes": _system_routes(result),
        "opening_skeleton_audits": _opening_audits(result),
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
