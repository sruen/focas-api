from __future__ import annotations

from collections import defaultdict

from .models import (
    MotiveReading,
    NarrativeAuditResult,
    NarrativeDirectionAudit,
    NarrativeMaterial,
    NaturalPull,
    OpeningMotiveReading,
)

DIRECTIONS = ("主胜", "平局", "客胜")


def _legacy_material(pull: NaturalPull) -> NarrativeMaterial:
    return NarrativeMaterial(
        direction=pull.direction,
        topic=pull.facts or f"{pull.direction}聚合题材",
        category="legacy_natural_pull",
        facts=pull.facts,
        visibility="LEGACY_AGGREGATE",
        strength=pull.strength,
        strength_alignment="UNCONFIRMED",
    )


def _is_structured(material: NarrativeMaterial) -> bool:
    return all(
        [
            material.topic,
            material.facts,
            material.source,
            material.published_at,
            material.visibility,
            material.strength,
            material.strength_alignment,
        ]
    )


def build_narrative_audit(
    *,
    pulls: list[NaturalPull],
    materials: list[NarrativeMaterial] | None = None,
    opening_readings: list[OpeningMotiveReading] | None = None,
    motive_readings: list[MotiveReading] | None = None,
) -> NarrativeAuditResult:
    """Audit available topics separately from evidence that institutions used them."""

    provided = list(materials or [])
    source_mode = "STRUCTURED_MATERIALS" if provided else "LEGACY_AGGREGATE_REVIEW_REQUIRED"
    if not provided:
        provided = [_legacy_material(pull) for pull in pulls]

    by_direction: dict[str, list[NarrativeMaterial]] = defaultdict(list)
    for material in provided:
        if material.direction in DIRECTIONS:
            by_direction[material.direction].append(material)

    inferred_use: dict[str, list[str]] = defaultdict(list)
    for reading in opening_readings or []:
        if reading.direction in DIRECTIONS and reading.uses_fundamental_pull:
            inferred_use[reading.direction].append(
                f"{reading.company}: opening interval comparison indicates use of visible fundamental pull"
            )
    for reading in motive_readings or []:
        if reading.direction in DIRECTIONS and reading.natural_pull_match not in {"", "UNCONFIRMED", "未确认"}:
            inferred_use[reading.direction].append(
                f"{reading.company}: {reading.action}; natural-pull match={reading.natural_pull_match}"
            )

    direction_audits: list[NarrativeDirectionAudit] = []
    complete = source_mode == "STRUCTURED_MATERIALS"
    for direction in DIRECTIONS:
        direction_materials = by_direction.get(direction, [])
        explicit_evidence = [
            evidence
            for material in direction_materials
            for evidence in material.institution_use_evidence
        ]
        evidence = [*explicit_evidence, *inferred_use.get(direction, [])]
        statuses = {material.institution_use_status for material in direction_materials}
        use_status = "USED" if evidence or "USED" in statuses else "NOT_USED" if statuses == {"NOT_USED"} else "UNCONFIRMED"
        structured = bool(direction_materials) and all(_is_structured(material) for material in direction_materials)
        complete = complete and structured
        notes: list[str] = []
        if not direction_materials:
            notes.append("No topic material was supplied for this direction.")
        if not structured:
            notes.append("Topic source, publication time, visibility, strength, or strength alignment still needs review.")
        direction_audits.append(
            NarrativeDirectionAudit(
                direction=direction,
                materials=direction_materials,
                available_topics=[material.topic for material in direction_materials],
                visibility=" / ".join(sorted({material.visibility or "UNCONFIRMED" for material in direction_materials})),
                strength=" / ".join(sorted({material.strength or "UNCONFIRMED" for material in direction_materials})),
                strength_alignment=" / ".join(
                    sorted({material.strength_alignment or "UNCONFIRMED" for material in direction_materials})
                ),
                institution_use_status=use_status,
                institution_use_evidence=evidence,
                notes=notes,
            )
        )

    notes = [
        "Topic exists != market impact; market impact != institutional use; institutional use != match outcome.",
    ]
    if source_mode != "STRUCTURED_MATERIALS":
        notes.append("Legacy natural_pulls were converted into aggregate topics. Add narrative_materials for source-level review.")
    if not complete:
        notes.append("Narrative audit is incomplete. Keep the conclusion at observe/PASS unless other evidence closes the chain.")
    return NarrativeAuditResult(
        direction_audits=direction_audits,
        source_mode=source_mode,
        complete=complete,
        review_required=not complete,
        notes=notes,
    )
