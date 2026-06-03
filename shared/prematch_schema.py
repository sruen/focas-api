"""Schema for the immutable pre-match snapshot."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .enums import DECISIONS, OUTCOMES
from .odds import IntervalCoordinates, OddsCoordinates, validate_interval_coordinates, validate_odds_coordinates
from .validators import (
    SharedValidationError,
    dict_copy,
    int_list,
    optional_str,
    require_bool,
    require_dict,
    require_keys,
    require_str,
    string_list,
)


@dataclass
class PrematchSnapshot:
    schema_version: str
    match_id: str
    competition: str | None
    home_team: str
    away_team: str
    match_time: str | None
    neutral_ground: bool | None
    source_type: str
    source_files: list[str]
    basic_face_complete: bool
    basic_face_gaps: list[str]
    home_strength_grade: str
    away_strength_grade: str
    strength_diff: str
    dynamic_revision: str | None
    theoretical_system: str | None
    theoretical_interval: str
    theoretical_interval_source: str | None
    actual_opening_interval: IntervalCoordinates
    actual_latest_interval: IntervalCoordinates
    opening_deviation: str | None
    odds_move_deviation: str | None
    original_distribution: dict[str, Any]
    company_motive_chain: dict[str, Any]
    unfavorable_directions: list[str]
    unfavorable_score_patterns: list[str]
    relative_mainline_selection: str
    final_direction: str
    score_range: list[str]
    margin_targets: list[int]
    evidence_gaps: list[str]
    companies: list[str]
    opening: OddsCoordinates
    latest_or_closing: OddsCoordinates
    final: OddsCoordinates | None
    odds_pattern_tags: list[str]
    company_alignment: str | None
    pre_match_summary: str | None
    decision_status: str = "UNCONFIRMED"
    structural_lean: str | None = None
    narrative_audit: dict[str, Any] = field(default_factory=dict)
    scenario_audit: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrematchSnapshot":
        data = require_dict(data, "prematch_snapshot")
        data = {
            "decision_status": "UNCONFIRMED",
            "structural_lean": None,
            "narrative_audit": {},
            "scenario_audit": {},
            **data,
        }
        keys = tuple(cls.__dataclass_fields__)
        require_keys(data, keys, "prematch_snapshot")
        if data["schema_version"] != "0.2":
            raise SharedValidationError("prematch_snapshot.schema_version must equal 0.2")
        unfavorable_directions = string_list(data["unfavorable_directions"], "prematch_snapshot.unfavorable_directions")
        if any(direction not in OUTCOMES for direction in unfavorable_directions):
            raise SharedValidationError("prematch_snapshot.unfavorable_directions values must be one of: 胜, 平, 负")
        final_direction = require_str(data["final_direction"], "prematch_snapshot.final_direction")
        if final_direction not in DECISIONS:
            raise SharedValidationError("prematch_snapshot.final_direction must be one of: 胜, 平, 负, PASS")
        margin_targets = int_list(data["margin_targets"], "prematch_snapshot.margin_targets")
        if any(target < 0 for target in margin_targets):
            raise SharedValidationError("prematch_snapshot.margin_targets values must be >= 0")
        company_motive_chain = dict_copy(data["company_motive_chain"], "prematch_snapshot.company_motive_chain")
        require_keys(company_motive_chain, ("opening", "movement", "closing"), "prematch_snapshot.company_motive_chain")
        final = data["final"]
        return cls(
            schema_version="0.2",
            match_id=require_str(data["match_id"], "prematch_snapshot.match_id", allow_empty=False),
            competition=optional_str(data["competition"], "prematch_snapshot.competition"),
            home_team=require_str(data["home_team"], "prematch_snapshot.home_team", allow_empty=False),
            away_team=require_str(data["away_team"], "prematch_snapshot.away_team", allow_empty=False),
            match_time=optional_str(data["match_time"], "prematch_snapshot.match_time"),
            neutral_ground=None if data["neutral_ground"] is None else require_bool(data["neutral_ground"], "prematch_snapshot.neutral_ground"),
            source_type=require_str(data["source_type"], "prematch_snapshot.source_type", allow_empty=False),
            source_files=string_list(data["source_files"], "prematch_snapshot.source_files"),
            basic_face_complete=require_bool(data["basic_face_complete"], "prematch_snapshot.basic_face_complete"),
            basic_face_gaps=string_list(data["basic_face_gaps"], "prematch_snapshot.basic_face_gaps"),
            home_strength_grade=require_str(data["home_strength_grade"], "prematch_snapshot.home_strength_grade", allow_empty=False),
            away_strength_grade=require_str(data["away_strength_grade"], "prematch_snapshot.away_strength_grade", allow_empty=False),
            strength_diff=require_str(data["strength_diff"], "prematch_snapshot.strength_diff", allow_empty=False),
            dynamic_revision=optional_str(data["dynamic_revision"], "prematch_snapshot.dynamic_revision"),
            theoretical_system=optional_str(data["theoretical_system"], "prematch_snapshot.theoretical_system"),
            theoretical_interval=require_str(data["theoretical_interval"], "prematch_snapshot.theoretical_interval", allow_empty=False),
            theoretical_interval_source=optional_str(data["theoretical_interval_source"], "prematch_snapshot.theoretical_interval_source"),
            actual_opening_interval=validate_interval_coordinates(data["actual_opening_interval"], "prematch_snapshot.actual_opening_interval"),
            actual_latest_interval=validate_interval_coordinates(data["actual_latest_interval"], "prematch_snapshot.actual_latest_interval"),
            opening_deviation=optional_str(data["opening_deviation"], "prematch_snapshot.opening_deviation"),
            odds_move_deviation=optional_str(data["odds_move_deviation"], "prematch_snapshot.odds_move_deviation"),
            original_distribution=dict_copy(data["original_distribution"], "prematch_snapshot.original_distribution"),
            company_motive_chain=company_motive_chain,
            unfavorable_directions=unfavorable_directions,
            unfavorable_score_patterns=string_list(data["unfavorable_score_patterns"], "prematch_snapshot.unfavorable_score_patterns"),
            relative_mainline_selection=require_str(data["relative_mainline_selection"], "prematch_snapshot.relative_mainline_selection", allow_empty=False),
            final_direction=final_direction,
            score_range=string_list(data["score_range"], "prematch_snapshot.score_range"),
            margin_targets=margin_targets,
            evidence_gaps=string_list(data["evidence_gaps"], "prematch_snapshot.evidence_gaps"),
            companies=string_list(data["companies"], "prematch_snapshot.companies"),
            opening=validate_odds_coordinates(data["opening"], "prematch_snapshot.opening"),
            latest_or_closing=validate_odds_coordinates(data["latest_or_closing"], "prematch_snapshot.latest_or_closing"),
            final=None if final is None else validate_odds_coordinates(final, "prematch_snapshot.final"),
            odds_pattern_tags=string_list(data["odds_pattern_tags"], "prematch_snapshot.odds_pattern_tags"),
            company_alignment=optional_str(data["company_alignment"], "prematch_snapshot.company_alignment"),
            pre_match_summary=optional_str(data["pre_match_summary"], "prematch_snapshot.pre_match_summary"),
            decision_status=require_str(data["decision_status"], "prematch_snapshot.decision_status", allow_empty=False),
            structural_lean=optional_str(data["structural_lean"], "prematch_snapshot.structural_lean"),
            narrative_audit=dict_copy(data["narrative_audit"], "prematch_snapshot.narrative_audit"),
            scenario_audit=dict_copy(data["scenario_audit"], "prematch_snapshot.scenario_audit"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
