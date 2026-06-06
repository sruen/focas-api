from __future__ import annotations

from .models import NarrativeAuditResult, ScenarioAuditResult, ScenarioCounterfactual

DIRECTIONS = ("主胜", "平局", "客胜")


def build_scenario_audit(*, result) -> ScenarioAuditResult:
    """Render the three counterfactual outcome scenarios before the final status."""

    hypothesis_by_direction = {
        item.direction: item
        for item in getattr(result.p1_core, "hypotheses", []) or []
    }
    narrative_by_direction = {
        item.direction: item
        for item in getattr(result.narrative_audit, "direction_audits", []) or []
    }
    judgement_by_direction = {
        item.direction: item
        for item in result.direction_judgements
    }
    adverse = set(getattr(result.integrated_structure, "adverse_excluded_directions", []) or [])
    qualified = set(getattr(result.integrated_structure, "mainline_qualified_directions", []) or [])

    scenarios: list[ScenarioCounterfactual] = []
    for direction in DIRECTIONS:
        hypothesis = hypothesis_by_direction.get(direction)
        narrative = narrative_by_direction.get(direction)
        judgement = judgement_by_direction.get(direction)
        contradictions: list[str] = []
        if direction in adverse:
            contradictions.append("Integrated structure formed an adverse evidence chain.")
        if direction not in qualified:
            contradictions.append("Supporting chain is not closed.")
        if narrative and narrative.institution_use_status == "UNCONFIRMED":
            contradictions.append("Institutional use of the available topic is unconfirmed.")
        scenarios.append(
            ScenarioCounterfactual(
                direction=direction,
                expected_structure=getattr(hypothesis, "expected_bookmaker_goal", "Scenario structure needs review."),
                supporting_evidence=[
                    *getattr(hypothesis, "required_support", []),
                    *([f"Available topics: {' / '.join(narrative.available_topics)}"] if narrative and narrative.available_topics else []),
                ],
                contradictions=contradictions,
                institution_use_evidence=list(getattr(narrative, "institution_use_evidence", []) or []),
                invalidation_conditions=list(getattr(hypothesis, "reality_check_questions", []) or []),
                status="ADVERSE" if direction in adverse else "QUALIFIED" if direction in qualified else "UNCONFIRMED",
            )
        )

    main = result.final_direction if result.final_direction not in {None, "PASS"} else result.structural_lean
    alternatives = [item.direction for item in scenarios if item.direction != main and item.status != "ADVERSE"]
    notes: list[str] = []
    if result.decision_status == "PASS":
        notes.append("No scenario completed the formal evidence chain. Structural lean is observation-only.")
    if getattr(result.narrative_audit, "review_required", False):
        notes.append("Narrative source-level audit is incomplete.")
    if result.skeleton_scope_status != "LOW_ODDS_AXIS_PRECISE":
        notes.append("Skeleton workbook low-odds axis status needs review.")
    return ScenarioAuditResult(
        scenarios=scenarios,
        main_scenario=main,
        alternative_scenario=alternatives[0] if alternatives else None,
        max_contradiction=notes[0] if notes else None,
        decision_status=result.decision_status,
        notes=notes,
    )
