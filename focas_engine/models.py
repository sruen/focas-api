from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GateResult:
    name: str
    ok: bool
    missing: List[str] = field(default_factory=list)
    reason: str = ""

    def stop_message(self) -> str:
        if self.ok:
            return f"{self.name}: PASS"
        miss = "、".join(self.missing) if self.missing else self.reason
        return f"{self.name}: STOP｜缺失：{miss}"


@dataclass
class TeamContext:
    name: str
    rank: Optional[str] = None
    points: Optional[str] = None
    recent_matches: List[str] = field(default_factory=list)
    venue_adaptation: Optional[str] = None
    attack_state: Optional[str] = None
    defense_state: Optional[str] = None
    injuries: Optional[str] = None
    schedule_fatigue: Optional[str] = None
    motivation: Optional[str] = None
    popularity_story: Optional[str] = None
    major_recent_matches: Optional[str] = None


@dataclass
class H2HContext:
    overall: Optional[str] = None
    recent_years: Optional[str] = None
    same_competition: Optional[str] = None
    venue_specific: Optional[str] = None
    latest_key_match: Optional[str] = None
    market_psychology: Optional[str] = None


@dataclass
class MatchContext:
    home_team: str
    away_team: str
    competition: Optional[str] = None
    kickoff_time: Optional[str] = None
    stage: Optional[str] = None
    neutral_venue: Optional[bool] = None
    single_leg: Optional[bool] = None
    match_type: Optional[str] = None
    extra_time_or_penalties: Optional[str] = None
    real_home_away: Optional[bool] = None
    attention_level: Optional[str] = None
    league_for_table: Optional[str] = None
    home: Optional[TeamContext] = None
    away: Optional[TeamContext] = None
    h2h: Optional[H2HContext] = None


@dataclass
class StrengthContext:
    home_grade: Optional[str] = None
    away_grade: Optional[str] = None
    static_gap: Optional[str] = None
    dynamic_adjustment: Optional[str] = None
    final_gap: Optional[str] = None
    original_distribution: Optional[str] = None
    theoretical_psychological_interval: Optional[str] = None
    theoretical_home_odds_range: Optional[str] = None
    theoretical_draw_odds_reference: Optional[str] = None
    theoretical_away_odds_reference: Optional[str] = None


@dataclass
class NaturalPull:
    direction: str
    strength: Optional[str] = None  # 强 / 中 / 弱
    facts: Optional[str] = None
    market_psychology: Optional[str] = None
    popularity_direction: Optional[str] = None
    easy_to_receive: Optional[bool] = None
    first_eye_direction: Optional[bool] = None


@dataclass
class NarrativeMaterial:
    direction: str
    topic: str
    category: Optional[str] = None
    facts: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    visibility: Optional[str] = None
    strength: Optional[str] = None
    strength_alignment: Optional[str] = None
    institution_use_status: str = "UNCONFIRMED"
    institution_use_evidence: List[str] = field(default_factory=list)
    utilization_mode: Optional[str] = None


@dataclass
class NarrativeDirectionAudit:
    direction: str
    materials: List[NarrativeMaterial] = field(default_factory=list)
    available_topics: List[str] = field(default_factory=list)
    visibility: str = "UNCONFIRMED"
    strength: str = "UNCONFIRMED"
    strength_alignment: str = "UNCONFIRMED"
    institution_use_status: str = "UNCONFIRMED"
    institution_use_evidence: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class NarrativeAuditResult:
    direction_audits: List[NarrativeDirectionAudit] = field(default_factory=list)
    source_mode: str = "LEGACY_AGGREGATE_REVIEW_REQUIRED"
    complete: bool = False
    review_required: bool = True
    notes: List[str] = field(default_factory=list)


@dataclass
class OriginalDistribution:
    distribution_type: str
    home_pressure: str
    draw_pressure: str
    away_pressure: str
    first_eye_direction: Optional[str]
    confidence_sources: List[str] = field(default_factory=list)
    weak_confidence_directions: List[str] = field(default_factory=list)
    dispersion_available: Dict[str, bool] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)


@dataclass
class OriginalBookMode:
    mode: Optional[str] = None
    reason: Optional[str] = None
    key_odds_to_watch: Optional[str] = None
    easiest_misread: Optional[str] = None
    source_classification: List[str] = field(default_factory=list)


@dataclass
class P1DirectionProfile:
    direction: str
    natural_pull: str
    original_distribution_strength: str
    confidence_carrying: str
    dispersion_support: str
    expected_board_style: str
    distribution_role: str
    can_bear_odds_raise: bool
    low_odds_decrease_meaning: str
    notes: List[str] = field(default_factory=list)


@dataclass
class P1MisreadBlock:
    pattern: str
    blocked_reason: str
    affected_directions: List[str] = field(default_factory=list)


@dataclass
class P1MainlineHypothesis:
    direction: str
    expected_bookmaker_goal: str
    required_support: List[str] = field(default_factory=list)
    reality_check_questions: List[str] = field(default_factory=list)


@dataclass
class P1CoreResult:
    distribution_type: str
    first_eye_direction: Optional[str]
    easiest_to_disperse_direction: Optional[str]
    profiles: List[P1DirectionProfile] = field(default_factory=list)
    hypotheses: List[P1MainlineHypothesis] = field(default_factory=list)
    misread_blocks: List[P1MisreadBlock] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class OddsSnapshot:
    home: float
    draw: float
    away: float

    def as_tuple(self) -> tuple[float, float, float]:
        return self.home, self.draw, self.away


@dataclass
class CompanyOdds:
    company: str  # William / Ladbrokes / Avg, or Chinese aliases
    initial: OddsSnapshot
    current: OddsSnapshot


@dataclass
class OddsSystemConversion:
    company: str
    snapshot_type: str
    raw_home: float
    raw_draw: float
    raw_away: float
    raw_payout_percent: float
    detected_system: str
    system_distance: float
    system_match_status: str
    target_system: str
    conversion_factor: float
    converted_home: float
    converted_draw: float
    converted_away: float
    conversion_status: str
    numerical_conversion_applied: bool = False
    system_routing_mode: str = "RETURN_RATE_SYSTEM_SHEET_ONLY"
    system_lookup_status: str = "SYSTEM_LOOKUP_FORBIDDEN"
    odds_type: str = ""
    odds_home: float = 0.0
    odds_draw: float = 0.0
    odds_away: float = 0.0
    calculated_return_rate: float = 0.0

    def raw_snapshot(self) -> OddsSnapshot:
        return OddsSnapshot(self.raw_home, self.raw_draw, self.raw_away)

    def comparison_snapshot(self) -> OddsSnapshot:
        """Return institution-published odds for lookup in the routed system sheet."""
        return self.raw_snapshot()

    def converted_snapshot(self) -> OddsSnapshot:
        """Backward-compatible alias. Odds values are no longer numerically converted."""
        return OddsSnapshot(self.converted_home, self.converted_draw, self.converted_away)


@dataclass
class TableLookupResult:
    company: str
    system: str
    league: str
    direction: str
    interval_id: Optional[int]
    water_band: Optional[str]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    table_reference_odds: Optional[float]
    actual_low_odds: float
    boundary_distance: Optional[float]
    deviation: str
    sheet_name: str
    row_number: Optional[int]
    lookup_status: str
    table_axis: str = "home"
    table_axis_odds: Optional[float] = None
    raw_row: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkeletonIntervalProfile:
    system: str
    sheet_name: str
    interval_id: int
    main_price_min: Optional[float]
    main_price_max: Optional[float]
    draw_reference_min: Optional[float]
    draw_reference_max: Optional[float]
    away_reference_min: Optional[float]
    away_reference_max: Optional[float]
    row_numbers: List[int] = field(default_factory=list)
    status: str = "UNCONFIRMED"
    notes: List[str] = field(default_factory=list)




@dataclass
class ExpectedOpeningInterval:
    final_gap_value: Optional[float]
    final_gap_label: str
    expected_low_side: str
    expected_interval_id: Optional[int]
    expected_water_band: Optional[str]
    source: str
    confidence: str
    rule: str
    notes: List[str] = field(default_factory=list)
    p4_strength_key: Optional[str] = None
    static_strength_gap: Optional[str] = None
    dynamic_adjustment: Optional[str] = None
    final_dynamic_strength_relation: Optional[str] = None
    expected_interval_source: str = "REVIEW_REQUIRED"
    matched_sheet: Optional[str] = None
    matched_row_id: Optional[str] = None
    matched_row_number: Optional[int] = None
    lookup_key_status: str = "NO_TABLE_MATCH"
    expected_interval: Optional[str] = None
    expected_interval_confidence: str = "REVIEW_REQUIRED"


@dataclass
class OpeningIntervalAudit:
    company: str
    opening_low_direction: str
    opening_low_odds: float
    opening_interval_id: Optional[int]
    opening_water_band: Optional[str]
    expected_low_side: str
    expected_interval_id: Optional[int]
    interval_delta: Optional[int]
    deviation_label: str
    semantic_tags: List[str] = field(default_factory=list)
    interpretation: str = ""
    hard_status: str = "UNCONFIRMED"
    system: Optional[str] = None
    sheet_name: Optional[str] = None
    raw_opening_home: Optional[float] = None
    raw_opening_draw: Optional[float] = None
    raw_opening_away: Optional[float] = None
    converted_opening_home: Optional[float] = None
    converted_opening_draw: Optional[float] = None
    converted_opening_away: Optional[float] = None
    expected_home_min: Optional[float] = None
    expected_home_max: Optional[float] = None
    expected_draw_reference_min: Optional[float] = None
    expected_draw_reference_max: Optional[float] = None
    expected_away_reference_min: Optional[float] = None
    expected_away_reference_max: Optional[float] = None
    home_range_deviation: Optional[float] = None
    draw_reference_deviation: Optional[float] = None
    away_reference_deviation: Optional[float] = None
    price_reasonableness: str = "UNCONFIRMED"
    skeleton_profile_status: str = "UNCONFIRMED"


@dataclass
class IntervalAuditResult:
    expected: Optional[ExpectedOpeningInterval] = None
    audits: List[OpeningIntervalAudit] = field(default_factory=list)
    ok: bool = False
    stop_reason: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class DirectionPsychologicalInterval:
    direction: str
    system: str
    interval_id: Optional[int]
    expected_water_band: Optional[str]
    odds_min: Optional[float]
    odds_max: Optional[float]
    precision: str
    profile_status: str
    notes: List[str] = field(default_factory=list)


@dataclass
class PsychologicalIntervalAudit:
    expected_interval_id: Optional[int]
    expected_water_band: Optional[str]
    expected_low_side: str
    systems: List[str] = field(default_factory=list)
    direction_intervals: List[DirectionPsychologicalInterval] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class OpeningBoardDirectionAudit:
    company: str
    system: str
    direction: str
    opening_odds: float
    current_odds: float
    action: str
    expected_min: Optional[float]
    expected_max: Optional[float]
    range_deviation: Optional[float]
    position_status: str
    semantic: str
    precision: str
    interval_id: Optional[int]
    water_band: Optional[str]


@dataclass
class OpeningBoardCompanyAudit:
    company: str
    system: str
    return_rate: float
    direction_audits: List[OpeningBoardDirectionAudit] = field(default_factory=list)


@dataclass
class OpeningBoardAudit:
    company_audits: List[OpeningBoardCompanyAudit] = field(default_factory=list)
    ok: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class MarketPullDirectionAudit:
    direction: str
    pull_strength: str
    pull_score: float
    pull_percent: float
    pull_label: str
    topic_sources: List[str] = field(default_factory=list)
    dispersion_available: bool = False
    first_eye_direction: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class MarketPullAudit:
    directions: List[MarketPullDirectionAudit] = field(default_factory=list)
    distribution_type: str = "UNCONFIRMED"
    notes: List[str] = field(default_factory=list)


@dataclass
class BookmakerTopicUsageDirection:
    direction: str
    available_topics: List[str] = field(default_factory=list)
    original_pull_percent: Optional[float] = None
    original_pull_label: str = "UNCONFIRMED"
    institution_use_status: str = "UNCONFIRMED"
    usage_mode: str = "UNCONFIRMED"
    used_evidence: List[str] = field(default_factory=list)
    unused_topics: List[str] = field(default_factory=list)
    unused_reason: Optional[str] = None


@dataclass
class BookmakerTopicUsageAudit:
    direction_usages: List[BookmakerTopicUsageDirection] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class OptimalScenario:
    target_direction: str
    required_topic_usage: List[str] = field(default_factory=list)
    supporting_directions: List[str] = field(default_factory=list)
    expected_interval_plan: Dict[str, str] = field(default_factory=dict)
    opening_fit: str = "UNCONFIRMED"
    movement_fit: str = "UNCONFIRMED"
    explanation_score: float = 0.0
    contradictions: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    status: str = "UNCONFIRMED"


@dataclass
class OptimalSolutionAudit:
    scenarios: List[OptimalScenario] = field(default_factory=list)
    solution_status: str = "UNCONFIRMED"
    selected_direction: Optional[str] = None
    better_solution_required: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class FutureAdjustmentItem:
    direction: str
    recommended_action: str
    target_psychological_interval: str
    purpose: str
    not_expected_to_hit_reason: Optional[str] = None


@dataclass
class FutureAdjustmentPlan:
    target_direction: Optional[str]
    items: List[FutureAdjustmentItem] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class FinalStructureJudgement:
    status: str
    direction: Optional[str]
    reason: str
    confidence: str
    warnings: List[str] = field(default_factory=list)


@dataclass
class EventContextModifiers:
    league_context_modifier: str
    event_type_modifier: str
    neutral_field_modifier: str
    attention_level_modifier: str
    home_advantage_modifier: str
    draw_tendency_modifier: str
    motivation_modifier: str
    schedule_modifier: str
    detected_event_tags: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return "；".join([
            self.league_context_modifier,
            self.event_type_modifier,
            self.neutral_field_modifier,
            self.attention_level_modifier,
            self.home_advantage_modifier,
            self.draw_tendency_modifier,
            self.motivation_modifier,
            self.schedule_modifier,
        ])


@dataclass
class OddsMove:
    company: str
    direction: str
    initial: float
    current: float
    delta: float
    action: str
    comparison_basis: str = "raw_odds"


@dataclass
class MotiveReading:
    company: str
    direction: str
    action: str
    natural_pull: Optional[str]
    confidence_carrying: str
    dispersion_effectiveness: str
    motive_type: str
    bookmaker_meaning: str
    adverse_evidence: bool
    target_direction: Optional[str] = None
    dispersion_target: Optional[str] = None
    protected_direction: Optional[str] = None
    attacked_direction: Optional[str] = None
    misread_risk: Optional[str] = None
    reasoning: List[str] = field(default_factory=list)
    table_interval_position: str = "未查表"
    company_purpose: str = "未形成公司目的解释"
    odds_move_semantics: str = "动作语义未形成"
    adverse_status: str = "未确认"
    return_incentive: str = "未确认"
    natural_pull_match: str = "未确认"


@dataclass
class OpeningMotiveReading:
    company: str
    direction: str
    opening_interval_id: Optional[int]
    expected_interval_id: Optional[int]
    interval_delta: Optional[int]
    natural_pull: str
    original_pressure: str
    first_eye_direction: Optional[str]
    uses_fundamental_pull: bool
    motive_type: str
    selection_constraint: str
    reasoning: List[str] = field(default_factory=list)


@dataclass
class CompanySemanticReading:
    company: str
    primary_focus: str
    semantic_role: str
    # v0.9.1 splits company semantics into three different evidence classes.
    # Only mainline_confirmed_directions may become hard double-company confirmation.
    # Risk repair and dispersion are useful evidence, but they are not direction confirmation.
    supported_directions: List[str] = field(default_factory=list)  # backward-compatible alias for mainline confirmations
    mainline_confirmed_directions: List[str] = field(default_factory=list)
    risk_repair_directions: List[str] = field(default_factory=list)
    dispersed_directions: List[str] = field(default_factory=list)
    adverse_pressure_directions: List[str] = field(default_factory=list)
    confirmation_level: str = "未确认"
    p1_connection: str = ""
    coordinate_connection: str = ""
    evidence: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CompanyRelationResult:
    relation_type: str
    readings: List[CompanySemanticReading] = field(default_factory=list)
    confirmed_directions: List[str] = field(default_factory=list)  # hard double-company mainline confirmation only
    mainline_confirmed_directions: List[str] = field(default_factory=list)
    risk_repair_directions: List[str] = field(default_factory=list)
    dispersion_directions: List[str] = field(default_factory=list)
    unconfirmed_directions: List[str] = field(default_factory=list)
    conflict_directions: List[str] = field(default_factory=list)
    adverse_pressure_directions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class DirectionJudgement:
    direction: str
    status: str  # 有利 / 中性 / 不利 / 未确认
    reasons: List[str] = field(default_factory=list)


@dataclass
class OddsFaceAndCompanyMotiveAnalysis:
    odds_face_shape: str
    william_motive: Optional[Any]
    ladbrokes_motive: Optional[Any]
    company_relation: Optional[Any]
    action_motive_chain: List[MotiveReading] = field(default_factory=list)
    misread_risks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    opening_motive_chain: List[OpeningMotiveReading] = field(default_factory=list)


@dataclass
class IntegratedStructureJudgement:
    home_integrated_judgement: str
    draw_integrated_judgement: str
    away_integrated_judgement: str
    adverse_excluded_directions: List[str] = field(default_factory=list)
    unconfirmed_directions: List[str] = field(default_factory=list)
    relative_weaker_directions: List[str] = field(default_factory=list)
    mainline_qualified_directions: List[str] = field(default_factory=list)
    summary_status: List[DirectionJudgement] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)


@dataclass
class RelativeSelectionScore:
    direction: str
    score: float
    selected: bool = False
    excluded_by_adverse: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class RelativeSelectionResult:
    selected_direction: str
    confidence: str
    method: str
    adverse_exclusions: List[str] = field(default_factory=list)
    relative_non_selected: List[str] = field(default_factory=list)
    scores: List[RelativeSelectionScore] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    score_margin: float = 0.0
    decision_eligible: bool = False


@dataclass
class ScenarioCounterfactual:
    direction: str
    expected_structure: str
    supporting_evidence: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    institution_use_evidence: List[str] = field(default_factory=list)
    invalidation_conditions: List[str] = field(default_factory=list)
    status: str = "UNCONFIRMED"


@dataclass
class ScenarioAuditResult:
    scenarios: List[ScenarioCounterfactual] = field(default_factory=list)
    main_scenario: Optional[str] = None
    alternative_scenario: Optional[str] = None
    max_contradiction: Optional[str] = None
    decision_status: str = "PASS"
    notes: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    gates: List[GateResult]
    basic_context_status: str = "UNCONFIRMED"
    odds_analysis_status: str = "FORBIDDEN"
    mainline_output_status: str = "FORBIDDEN"
    report_mode: str = "STOP_REPORT_ONLY"
    table_read_confirmed: str = "NO"
    hard_data_source: str = ""
    expected_interval_status: str = "REVIEW_REQUIRED"
    strength_source: str = "MANUAL_REVIEW_REQUIRED"
    missing_fields: List[str] = field(default_factory=list)
    stop_node: Optional[str] = None
    strength_context: Optional[StrengthContext] = None
    strength_estimate: Optional[Any] = None
    original_distribution: Optional[OriginalDistribution] = None
    book_mode_context: Optional[OriginalBookMode] = None
    original_mode_estimate: Optional[Any] = None
    p1_core: Optional[Any] = None
    context_modifiers: Optional[EventContextModifiers] = None
    odds_system_conversions: List[OddsSystemConversion] = field(default_factory=list)
    table_results: List[TableLookupResult] = field(default_factory=list)
    odds_coordinates: Optional[Any] = None
    expected_opening_interval: Optional[ExpectedOpeningInterval] = None
    interval_audit: Optional[Any] = None
    odds_moves: List[OddsMove] = field(default_factory=list)
    motive_readings: List[MotiveReading] = field(default_factory=list)
    company_semantics: Optional[Any] = None
    stage_9_analysis: Optional[OddsFaceAndCompanyMotiveAnalysis] = None
    integrated_structure: Optional[IntegratedStructureJudgement] = None
    direction_judgements: List[DirectionJudgement] = field(default_factory=list)
    narrative_audit: Optional[NarrativeAuditResult] = None
    scenario_audit: Optional[ScenarioAuditResult] = None
    psychological_interval_audit: Optional[PsychologicalIntervalAudit] = None
    opening_board_audit: Optional[OpeningBoardAudit] = None
    market_pull_audit: Optional[MarketPullAudit] = None
    bookmaker_topic_usage_audit: Optional[BookmakerTopicUsageAudit] = None
    optimal_solution_audit: Optional[OptimalSolutionAudit] = None
    future_adjustment_plan: Optional[FutureAdjustmentPlan] = None
    final_structure_judgement: Optional[FinalStructureJudgement] = None
    decision_status: str = "PASS"
    structural_lean: Optional[str] = None
    skeleton_scope_status: str = "HOME_AXIS_ONLY"
    stop: bool = False
    stop_reason: Optional[str] = None
    final_direction: Optional[str] = None
    relative_selection: Optional[Any] = None
    notes: List[str] = field(default_factory=list)
