"""Schema definitions for FOCAS post-match fact samples."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar


class SchemaValidationError(ValueError):
    """Raised when a post-match sample does not satisfy the schema."""


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{path} must be a dict")
    return value


def _require_keys(data: dict[str, Any], keys: tuple[str, ...], path: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise SchemaValidationError(f"{path} missing required fields: {', '.join(missing)}")


def _require_str(value: Any, path: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(f"{path} must be a str")
    if not allow_empty and not value.strip():
        raise SchemaValidationError(f"{path} must not be empty")
    return value


def _optional_str(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, path)


def _require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(f"{path} must be a bool")
    return value


def _optional_bool(value: Any, path: str) -> bool | None:
    if value is None:
        return None
    return _require_bool(value, path)


def _require_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(f"{path} must be an int")
    return value


def _string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{path} must be a list")
    return [_require_str(item, f"{path}[{index}]") for index, item in enumerate(value)]


def _int_list(value: Any, path: str) -> list[int]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{path} must be a list")
    return [_require_int(item, f"{path}[{index}]") for index, item in enumerate(value)]


def _dict_list(value: Any, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{path} must be a list")
    return [deepcopy(_require_dict(item, f"{path}[{index}]")) for index, item in enumerate(value)]


def _odds_coordinates(value: Any, path: str) -> dict[str, list[int | float]]:
    companies = _require_dict(value, path)
    coordinates: dict[str, list[int | float]] = {}
    for company, odds in companies.items():
        _require_str(company, f"{path} company", allow_empty=False)
        if not isinstance(odds, list) or len(odds) != 3:
            raise SchemaValidationError(f"{path}.{company} must contain exactly [胜, 平, 负] odds")
        checked: list[int | float] = []
        for index, odd in enumerate(odds):
            if not isinstance(odd, (int, float)) or isinstance(odd, bool):
                raise SchemaValidationError(f"{path}.{company}[{index}] must be an int or float")
            if odd <= 1.0:
                raise SchemaValidationError(f"{path}.{company}[{index}] must be > 1.0")
            checked.append(odd)
        coordinates[company] = checked
    return coordinates


def _interval_coordinates(value: Any, path: str) -> dict[str, dict[str, str]]:
    companies = _require_dict(value, path)
    coordinates: dict[str, dict[str, str]] = {}
    for company, intervals in companies.items():
        _require_str(company, f"{path} company", allow_empty=False)
        company_intervals = _require_dict(intervals, f"{path}.{company}")
        _require_keys(company_intervals, ("home", "draw", "away"), f"{path}.{company}")
        coordinates[company] = {
            direction: _require_str(
                company_intervals[direction],
                f"{path}.{company}.{direction}",
                allow_empty=False,
            )
            for direction in ("home", "draw", "away")
        }
    return coordinates


@dataclass
class MatchInfo:
    home_team: str
    away_team: str
    competition: str | None
    match_date: str | None
    neutral_ground: bool | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchInfo":
        data = _require_dict(data, "match")
        _require_keys(data, ("home_team", "away_team", "competition", "match_date", "neutral_ground"), "match")
        return cls(
            home_team=_require_str(data["home_team"], "match.home_team", allow_empty=False),
            away_team=_require_str(data["away_team"], "match.away_team", allow_empty=False),
            competition=_optional_str(data["competition"], "match.competition"),
            match_date=_optional_str(data["match_date"], "match.match_date"),
            neutral_ground=_optional_bool(data["neutral_ground"], "match.neutral_ground"),
        )


@dataclass
class PreMatchInfo:
    final_direction: str
    score_range: list[str]
    margin_targets: list[int]
    margin_view: str | None
    pre_match_summary: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreMatchInfo":
        data = _require_dict(data, "pre_match")
        _require_keys(
            data,
            ("final_direction", "score_range", "margin_targets", "margin_view", "pre_match_summary"),
            "pre_match",
        )
        final_direction = _require_str(data["final_direction"], "pre_match.final_direction")
        if final_direction not in PostmatchSample.OUTCOMES | {"PASS"}:
            raise SchemaValidationError("pre_match.final_direction must be one of: 胜, 平, 负, PASS")
        margin_targets = _int_list(data["margin_targets"], "pre_match.margin_targets")
        if any(target < 0 for target in margin_targets):
            raise SchemaValidationError("pre_match.margin_targets values must be >= 0")
        return cls(
            final_direction=final_direction,
            score_range=_string_list(data["score_range"], "pre_match.score_range"),
            margin_targets=margin_targets,
            margin_view=_optional_str(data["margin_view"], "pre_match.margin_view"),
            pre_match_summary=_optional_str(data["pre_match_summary"], "pre_match.pre_match_summary"),
        )


@dataclass
class PreMatchStructure:
    basic_face_complete: bool
    basic_face_gaps: list[str]
    home_strength_grade: str
    away_strength_grade: str
    strength_diff: str
    dynamic_revision: str | None
    theoretical_system: str | None
    theoretical_interval: str
    theoretical_interval_source: str | None
    actual_opening_interval: dict[str, dict[str, str]]
    actual_latest_interval: dict[str, dict[str, str]]
    opening_deviation: str | None
    odds_move_deviation: str | None
    original_distribution: dict[str, Any]
    unfavorable_directions: list[str]
    unfavorable_score_patterns: list[str]
    relative_mainline_selection: str
    company_motive_chain: dict[str, Any]
    evidence_gaps: list[str]
    decision_status: str = "LEGACY_UNCONFIRMED"
    structural_lean: str | None = None
    narrative_audit: dict[str, Any] = field(default_factory=dict)
    scenario_audit: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreMatchStructure":
        data = _require_dict(data, "pre_match_structure")
        data = {
            "decision_status": "LEGACY_UNCONFIRMED",
            "structural_lean": None,
            "narrative_audit": {},
            "scenario_audit": {},
            **data,
        }
        keys = (
            "basic_face_complete",
            "basic_face_gaps",
            "home_strength_grade",
            "away_strength_grade",
            "strength_diff",
            "dynamic_revision",
            "theoretical_system",
            "theoretical_interval",
            "theoretical_interval_source",
            "actual_opening_interval",
            "actual_latest_interval",
            "opening_deviation",
            "odds_move_deviation",
            "original_distribution",
            "unfavorable_directions",
            "unfavorable_score_patterns",
            "relative_mainline_selection",
            "company_motive_chain",
            "evidence_gaps",
            "decision_status",
            "structural_lean",
            "narrative_audit",
            "scenario_audit",
        )
        _require_keys(data, keys, "pre_match_structure")
        company_motive_chain = _require_dict(data["company_motive_chain"], "pre_match_structure.company_motive_chain")
        _require_keys(company_motive_chain, ("opening", "movement", "closing"), "pre_match_structure.company_motive_chain")
        unfavorable_directions = _string_list(
            data["unfavorable_directions"], "pre_match_structure.unfavorable_directions"
        )
        if any(direction not in PostmatchSample.OUTCOMES for direction in unfavorable_directions):
            raise SchemaValidationError("pre_match_structure.unfavorable_directions values must be one of: 胜, 平, 负")
        return cls(
            basic_face_complete=_require_bool(data["basic_face_complete"], "pre_match_structure.basic_face_complete"),
            basic_face_gaps=_string_list(data["basic_face_gaps"], "pre_match_structure.basic_face_gaps"),
            home_strength_grade=_require_str(
                data["home_strength_grade"], "pre_match_structure.home_strength_grade", allow_empty=False
            ),
            away_strength_grade=_require_str(
                data["away_strength_grade"], "pre_match_structure.away_strength_grade", allow_empty=False
            ),
            strength_diff=_require_str(data["strength_diff"], "pre_match_structure.strength_diff", allow_empty=False),
            dynamic_revision=_optional_str(data["dynamic_revision"], "pre_match_structure.dynamic_revision"),
            theoretical_system=_optional_str(data["theoretical_system"], "pre_match_structure.theoretical_system"),
            theoretical_interval=_require_str(
                data["theoretical_interval"], "pre_match_structure.theoretical_interval", allow_empty=False
            ),
            theoretical_interval_source=_optional_str(
                data["theoretical_interval_source"], "pre_match_structure.theoretical_interval_source"
            ),
            actual_opening_interval=_interval_coordinates(
                data["actual_opening_interval"], "pre_match_structure.actual_opening_interval"
            ),
            actual_latest_interval=_interval_coordinates(
                data["actual_latest_interval"], "pre_match_structure.actual_latest_interval"
            ),
            opening_deviation=_optional_str(data["opening_deviation"], "pre_match_structure.opening_deviation"),
            odds_move_deviation=_optional_str(data["odds_move_deviation"], "pre_match_structure.odds_move_deviation"),
            original_distribution=deepcopy(
                _require_dict(data["original_distribution"], "pre_match_structure.original_distribution")
            ),
            unfavorable_directions=unfavorable_directions,
            unfavorable_score_patterns=_string_list(
                data["unfavorable_score_patterns"], "pre_match_structure.unfavorable_score_patterns"
            ),
            relative_mainline_selection=_require_str(
                data["relative_mainline_selection"],
                "pre_match_structure.relative_mainline_selection",
                allow_empty=False,
            ),
            company_motive_chain=deepcopy(company_motive_chain),
            evidence_gaps=_string_list(data["evidence_gaps"], "pre_match_structure.evidence_gaps"),
            decision_status=_require_str(data["decision_status"], "pre_match_structure.decision_status", allow_empty=False),
            structural_lean=_optional_str(data["structural_lean"], "pre_match_structure.structural_lean"),
            narrative_audit=deepcopy(_require_dict(data["narrative_audit"], "pre_match_structure.narrative_audit")),
            scenario_audit=deepcopy(_require_dict(data["scenario_audit"], "pre_match_structure.scenario_audit")),
        )

    def core_fields_complete(self) -> bool:
        """Return whether the structured snapshot is complete enough for promotion."""

        return (
            self.basic_face_complete
            and not self.basic_face_gaps
            and bool(self.home_strength_grade.strip())
            and bool(self.away_strength_grade.strip())
            and bool(self.strength_diff.strip())
            and bool(self.theoretical_interval.strip())
            and bool(self.actual_opening_interval)
            and bool(self.actual_latest_interval)
            and bool(self.original_distribution)
            and bool(self.relative_mainline_selection.strip())
            and all(self.company_motive_chain.get(stage) for stage in ("opening", "movement", "closing"))
            and not self.evidence_gaps
            and self.decision_status not in {"PASS", "OBSERVE"}
        )


@dataclass
class OddsInfo:
    companies: list[str]
    opening: dict[str, list[int | float]]
    latest_or_closing: dict[str, list[int | float]]
    final: dict[str, list[int | float]] | None
    odds_pattern_tags: list[str]
    company_alignment: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OddsInfo":
        data = _require_dict(data, "odds")
        _require_keys(
            data,
            ("companies", "opening", "latest_or_closing", "final", "odds_pattern_tags", "company_alignment"),
            "odds",
        )
        final = data["final"]
        return cls(
            companies=_string_list(data["companies"], "odds.companies"),
            opening=_odds_coordinates(data["opening"], "odds.opening"),
            latest_or_closing=_odds_coordinates(data["latest_or_closing"], "odds.latest_or_closing"),
            final=None if final is None else _odds_coordinates(final, "odds.final"),
            odds_pattern_tags=_string_list(data["odds_pattern_tags"], "odds.odds_pattern_tags"),
            company_alignment=_optional_str(data["company_alignment"], "odds.company_alignment"),
        )


@dataclass
class ResultInfo:
    final_score: str
    outcome: str
    home_goals: int
    away_goals: int
    goal_margin: int
    key_events: list[dict[str, Any]]
    red_cards: list[dict[str, Any]]
    stats: dict[str, Any] | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResultInfo":
        data = _require_dict(data, "result")
        _require_keys(
            data,
            ("final_score", "outcome", "home_goals", "away_goals", "goal_margin", "key_events", "red_cards", "stats"),
            "result",
        )
        final_score = _require_str(data["final_score"], "result.final_score", allow_empty=False)
        outcome = _require_str(data["outcome"], "result.outcome")
        home_goals = _require_int(data["home_goals"], "result.home_goals")
        away_goals = _require_int(data["away_goals"], "result.away_goals")
        goal_margin = _require_int(data["goal_margin"], "result.goal_margin")
        expected_score = f"{home_goals}-{away_goals}"
        if final_score != expected_score:
            raise SchemaValidationError(f"result.final_score must equal {expected_score}")
        expected_margin = home_goals - away_goals
        if goal_margin != expected_margin:
            raise SchemaValidationError(f"result.goal_margin must equal {expected_margin}")
        expected_outcome = "胜" if expected_margin > 0 else "负" if expected_margin < 0 else "平"
        if outcome != expected_outcome:
            raise SchemaValidationError(f"result.outcome must equal {expected_outcome} based on score")
        return cls(
            final_score=final_score,
            outcome=outcome,
            home_goals=home_goals,
            away_goals=away_goals,
            goal_margin=goal_margin,
            key_events=_dict_list(data["key_events"], "result.key_events"),
            red_cards=_dict_list(data["red_cards"], "result.red_cards"),
            stats=None if data["stats"] is None else deepcopy(_require_dict(data["stats"], "result.stats")),
        )


@dataclass
class ValidationInfo:
    direction_hit: bool
    score_range_hit: bool
    margin_hit: bool
    logic_hit: bool | None
    process_risk_covered: bool | None
    validation_summary: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationInfo":
        data = _require_dict(data, "validation")
        _require_keys(
            data,
            ("direction_hit", "score_range_hit", "margin_hit", "logic_hit", "process_risk_covered", "validation_summary"),
            "validation",
        )
        return cls(
            direction_hit=_require_bool(data["direction_hit"], "validation.direction_hit"),
            score_range_hit=_require_bool(data["score_range_hit"], "validation.score_range_hit"),
            margin_hit=_require_bool(data["margin_hit"], "validation.margin_hit"),
            logic_hit=_optional_bool(data["logic_hit"], "validation.logic_hit"),
            process_risk_covered=_optional_bool(data["process_risk_covered"], "validation.process_risk_covered"),
            validation_summary=_require_str(data["validation_summary"], "validation.validation_summary"),
        )

    def validate_against(self, pre_match: PreMatchInfo, result: ResultInfo) -> None:
        expected_direction_hit = pre_match.final_direction == result.outcome
        if self.direction_hit != expected_direction_hit:
            raise SchemaValidationError(f"validation.direction_hit must equal {expected_direction_hit}")
        expected_score_range_hit = result.final_score in pre_match.score_range
        if self.score_range_hit != expected_score_range_hit:
            raise SchemaValidationError(f"validation.score_range_hit must equal {expected_score_range_hit}")
        expected_margin_hit = bool(pre_match.margin_targets) and abs(result.goal_margin) in pre_match.margin_targets
        if self.margin_hit != expected_margin_hit:
            raise SchemaValidationError(f"validation.margin_hit must equal {expected_margin_hit}")
        if not pre_match.margin_targets and "无法验证幅度" not in self.validation_summary:
            raise SchemaValidationError("validation.validation_summary must explain 无法验证幅度 when margin_targets is empty")


@dataclass
class ThreeWayReview:
    win_review: str
    draw_review: str
    loss_review: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThreeWayReview":
        data = _require_dict(data, "three_way_review")
        _require_keys(data, ("win_review", "draw_review", "loss_review"), "three_way_review")
        return cls(
            win_review=_require_str(data["win_review"], "three_way_review.win_review"),
            draw_review=_require_str(data["draw_review"], "three_way_review.draw_review"),
            loss_review=_require_str(data["loss_review"], "three_way_review.loss_review"),
        )


@dataclass
class LogicAudit:
    basic_face_validated: str | None
    strength_grade_validated: str | None
    original_distribution_validated: str | None
    opening_odds_validated: str | None
    odds_move_validated: str | None
    flat_odds_validated: str | None
    company_motive_validated: str | None
    trading_volume_validated: str | None
    special_variables: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogicAudit":
        data = _require_dict(data, "logic_audit")
        keys = (
            "basic_face_validated",
            "strength_grade_validated",
            "original_distribution_validated",
            "opening_odds_validated",
            "odds_move_validated",
            "flat_odds_validated",
            "company_motive_validated",
            "trading_volume_validated",
            "special_variables",
        )
        _require_keys(data, keys, "logic_audit")
        return cls(
            basic_face_validated=_optional_str(data["basic_face_validated"], "logic_audit.basic_face_validated"),
            strength_grade_validated=_optional_str(data["strength_grade_validated"], "logic_audit.strength_grade_validated"),
            original_distribution_validated=_optional_str(
                data["original_distribution_validated"], "logic_audit.original_distribution_validated"
            ),
            opening_odds_validated=_optional_str(data["opening_odds_validated"], "logic_audit.opening_odds_validated"),
            odds_move_validated=_optional_str(data["odds_move_validated"], "logic_audit.odds_move_validated"),
            flat_odds_validated=_optional_str(data["flat_odds_validated"], "logic_audit.flat_odds_validated"),
            company_motive_validated=_optional_str(
                data["company_motive_validated"], "logic_audit.company_motive_validated"
            ),
            trading_volume_validated=_optional_str(
                data["trading_volume_validated"], "logic_audit.trading_volume_validated"
            ),
            special_variables=_string_list(data["special_variables"], "logic_audit.special_variables"),
        )


@dataclass
class ErrorOrSuccess:
    primary_type: str
    secondary_types: list[str]
    explanation: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorOrSuccess":
        data = _require_dict(data, "error_or_success")
        _require_keys(data, ("primary_type", "secondary_types", "explanation"), "error_or_success")
        return cls(
            primary_type=_require_str(data["primary_type"], "error_or_success.primary_type"),
            secondary_types=_string_list(data["secondary_types"], "error_or_success.secondary_types"),
            explanation=_require_str(data["explanation"], "error_or_success.explanation"),
        )


@dataclass
class TagsInfo:
    structure_tags: list[str]
    error_tags: list[str]
    company_tags: list[str]
    odds_tags: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TagsInfo":
        data = _require_dict(data, "tags")
        _require_keys(data, ("structure_tags", "error_tags", "company_tags", "odds_tags"), "tags")
        return cls(
            structure_tags=_string_list(data["structure_tags"], "tags.structure_tags"),
            error_tags=_string_list(data["error_tags"], "tags.error_tags"),
            company_tags=_string_list(data["company_tags"], "tags.company_tags"),
            odds_tags=_string_list(data["odds_tags"], "tags.odds_tags"),
        )


@dataclass
class LessonInfo:
    reusable_pattern: str | None
    candidate_rule: str | None
    overfit_warning: str | None
    next_time_questions: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LessonInfo":
        data = _require_dict(data, "lesson")
        _require_keys(data, ("reusable_pattern", "candidate_rule", "overfit_warning", "next_time_questions"), "lesson")
        return cls(
            reusable_pattern=_optional_str(data["reusable_pattern"], "lesson.reusable_pattern"),
            candidate_rule=_optional_str(data["candidate_rule"], "lesson.candidate_rule"),
            overfit_warning=_optional_str(data["overfit_warning"], "lesson.overfit_warning"),
            next_time_questions=_string_list(data["next_time_questions"], "lesson.next_time_questions"),
        )


@dataclass
class PromotionInfo:
    status: str
    similar_sample_key: str | None
    similar_sample_count: int
    promotion_reason: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromotionInfo":
        data = _require_dict(data, "promotion")
        _require_keys(data, ("status", "similar_sample_key", "similar_sample_count", "promotion_reason"), "promotion")
        status = _require_str(data["status"], "promotion.status")
        if status not in PostmatchSample.PROMOTION_STATUSES:
            raise SchemaValidationError(
                "promotion.status must be one of: candidate, watch, usable, rule_candidate, rejected"
            )
        count = _require_int(data["similar_sample_count"], "promotion.similar_sample_count")
        if count < 0:
            raise SchemaValidationError("promotion.similar_sample_count must be >= 0")
        return cls(
            status=status,
            similar_sample_key=_optional_str(data["similar_sample_key"], "promotion.similar_sample_key"),
            similar_sample_count=count,
            promotion_reason=_optional_str(data["promotion_reason"], "promotion.promotion_reason"),
        )


@dataclass
class PostmatchSample:
    schema_version: str
    sample_id: str
    match_id: str | None
    created_at: str
    updated_at: str
    source_type: str
    source_files: list[str]
    distribution_fingerprint: dict[str, Any]
    interval_fingerprint: dict[str, Any]
    movement_fingerprint: dict[str, Any]
    structure_key_coarse: str
    structure_key_exact: str
    movement_key: str
    decision_key: str
    match: MatchInfo
    pre_match: PreMatchInfo
    pre_match_structure: PreMatchStructure
    odds: OddsInfo
    result: ResultInfo
    validation: ValidationInfo
    three_way_review: ThreeWayReview
    logic_audit: LogicAudit
    error_or_success: ErrorOrSuccess
    tags: TagsInfo
    lesson: LessonInfo
    promotion: PromotionInfo

    OUTCOMES: ClassVar[frozenset[str]] = frozenset({"胜", "平", "负"})
    PROMOTION_STATUSES: ClassVar[frozenset[str]] = frozenset(
        {"candidate", "watch", "usable", "rule_candidate", "rejected"}
    )
    SCHEMA_VERSION: ClassVar[str] = "0.2"

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, require_sample_id: bool = False) -> "PostmatchSample":
        data = _require_dict(data, "sample")
        keys = (
            "schema_version",
            "match_id",
            "created_at",
            "updated_at",
            "source_type",
            "source_files",
            "match",
            "pre_match",
            "pre_match_structure",
            "odds",
            "result",
            "validation",
            "three_way_review",
            "logic_audit",
            "error_or_success",
            "tags",
            "lesson",
            "promotion",
        )
        _require_keys(data, keys, "sample")
        schema_version = _require_str(data["schema_version"], "sample.schema_version")
        if schema_version != cls.SCHEMA_VERSION:
            raise SchemaValidationError(f"sample.schema_version must equal {cls.SCHEMA_VERSION}")
        sample_id = _require_str(data.get("sample_id", ""), "sample.sample_id")
        if require_sample_id and not sample_id.strip():
            raise SchemaValidationError("sample.sample_id must not be empty")
        pre_match = PreMatchInfo.from_dict(data["pre_match"])
        result = ResultInfo.from_dict(data["result"])
        validation = ValidationInfo.from_dict(data["validation"])
        validation.validate_against(pre_match, result)
        return cls(
            schema_version=schema_version,
            sample_id=sample_id,
            match_id=_optional_str(data["match_id"], "sample.match_id"),
            created_at=_require_str(data["created_at"], "sample.created_at", allow_empty=False),
            updated_at=_require_str(data["updated_at"], "sample.updated_at", allow_empty=False),
            source_type=_require_str(data["source_type"], "sample.source_type", allow_empty=False),
            source_files=_string_list(data["source_files"], "sample.source_files"),
            # Empty defaults keep existing v0.2 JSONL readable. New reviews always
            # persist populated v1.1.2 fingerprints before entering storage.
            distribution_fingerprint=deepcopy(
                _require_dict(data.get("distribution_fingerprint", {}), "sample.distribution_fingerprint")
            ),
            interval_fingerprint=deepcopy(
                _require_dict(data.get("interval_fingerprint", {}), "sample.interval_fingerprint")
            ),
            movement_fingerprint=deepcopy(
                _require_dict(data.get("movement_fingerprint", {}), "sample.movement_fingerprint")
            ),
            structure_key_coarse=_require_str(data.get("structure_key_coarse", ""), "sample.structure_key_coarse"),
            structure_key_exact=_require_str(data.get("structure_key_exact", ""), "sample.structure_key_exact"),
            movement_key=_require_str(data.get("movement_key", ""), "sample.movement_key"),
            decision_key=_require_str(data.get("decision_key", ""), "sample.decision_key"),
            match=MatchInfo.from_dict(data["match"]),
            pre_match=pre_match,
            pre_match_structure=PreMatchStructure.from_dict(data["pre_match_structure"]),
            odds=OddsInfo.from_dict(data["odds"]),
            result=result,
            validation=validation,
            three_way_review=ThreeWayReview.from_dict(data["three_way_review"]),
            logic_audit=LogicAudit.from_dict(data["logic_audit"]),
            error_or_success=ErrorOrSuccess.from_dict(data["error_or_success"]),
            tags=TagsInfo.from_dict(data["tags"]),
            lesson=LessonInfo.from_dict(data["lesson"]),
            promotion=PromotionInfo.from_dict(data["promotion"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the sample."""

        return asdict(self)

    def validate(self, *, require_sample_id: bool = False) -> None:
        """Validate this instance by round-tripping through the schema parser."""

        self.from_dict(self.to_dict(), require_sample_id=require_sample_id)
