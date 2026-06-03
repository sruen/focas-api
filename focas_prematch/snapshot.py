"""Run the existing FOCAS pipeline and emit an immutable pre-match snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from focas_engine.config import HARD_DATA_SOURCE
from focas_engine.io import LoadedInput, load_input_with_report
from focas_engine.odds_system import normalize_company
from focas_engine.pipeline import FocasPipeline
from shared.enums import PREMATCH_TO_OUTCOME
from shared.fingerprint import build_fingerprint
from shared.prematch_schema import PrematchSnapshot

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TABLE_PATH = PROJECT_ROOT / HARD_DATA_SOURCE


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _match_id(loaded: LoadedInput) -> str:
    raw_match = loaded.raw.get("match", {})
    explicit = loaded.raw.get("match_id") or raw_match.get("match_id")
    if explicit:
        return str(explicit)
    text = "|".join(
        [
            loaded.match.competition or "",
            loaded.match.home_team,
            loaded.match.away_team,
            loaded.match.kickoff_time or "",
        ]
    )
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", text).strip("-")[:48]
    return f"{slug}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]}"


def _score_defaults(direction: str) -> tuple[list[str], list[int]]:
    if direction == "PASS":
        return [], []
    if direction == "胜":
        return ["1-0", "2-0", "2-1"], [1, 2]
    if direction == "平":
        return ["0-0", "1-1", "2-2"], [0]
    return ["0-1", "0-2", "1-2"], [1, 2]


def _coordinate_label(coordinate: Any) -> str:
    interval = f"{coordinate.interval_id}区" if coordinate.interval_id is not None else "区间未确认"
    water = coordinate.water_band or "水位未确认"
    return f"{interval}{water}｜{coordinate.deviation}"


def _interval_coordinates(loaded: LoadedInput, result: Any, time_point: str) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    raw_by_company = {normalize_company(item.company): item for item in loaded.odds}
    coordinate_by_company: dict[str, Any] = {}
    if result.odds_coordinates:
        for company_set in result.odds_coordinates.company_sets:
            for coordinate in company_set.coordinates:
                if coordinate.time_point == time_point:
                    coordinate_by_company[normalize_company(company_set.company)] = coordinate
    for company, company_odds in raw_by_company.items():
        snapshot = company_odds.initial if time_point == "initial" else company_odds.current
        values[company] = {
            "home": f"组合参考｜赔率={snapshot.home:.3f}",
            "draw": f"组合参考｜赔率={snapshot.draw:.3f}",
            "away": f"组合参考｜赔率={snapshot.away:.3f}",
        }
        coordinate = coordinate_by_company.get(company)
        if coordinate:
            values[company]["home"] = _coordinate_label(coordinate)
    return values


def _odds_coordinates(loaded: LoadedInput, snapshot_type: str) -> dict[str, list[float]]:
    coordinates: dict[str, list[float]] = {}
    for item in loaded.odds:
        company = normalize_company(item.company)
        snapshot = item.initial if snapshot_type == "initial" else item.current
        coordinates[company] = [snapshot.home, snapshot.draw, snapshot.away]
    return coordinates


def _opening_deviation(result: Any) -> str | None:
    interval_audit = result.interval_audit
    if not interval_audit or not interval_audit.audits:
        return None
    return "；".join(
        f"{item.company}:{item.system or '体系未确认'}:{item.opening_interval_id}区/"
        f"{item.opening_water_band or '水位未确认'}:{item.price_reasonableness}:{item.deviation_label}"
        for item in interval_audit.audits
    )


def _movement_deviation(result: Any) -> str | None:
    if not result.odds_moves:
        return None
    return "；".join(f"{item.company}:{item.direction}:{item.action}:{item.delta:+.3f}" for item in result.odds_moves)


def _company_motive_chain(result: Any) -> dict[str, Any]:
    stage = result.stage_9_analysis
    interval_audit = result.interval_audit
    return {
        "opening": {
            "expected_interval": asdict(result.expected_opening_interval) if result.expected_opening_interval else {},
            "skeleton_audits": [asdict(item) for item in interval_audit.audits] if interval_audit else [],
            "readings": [asdict(item) for item in getattr(stage, "opening_motive_chain", [])] if stage else [],
        },
        "movement": {
            "moves": [asdict(item) for item in result.odds_moves],
            "motive_readings": [asdict(item) for item in result.motive_readings],
            "odds_face_change": getattr(stage, "odds_face_shape", None) if stage else None,
        },
        "closing": {
            "company_relation": asdict(result.company_semantics) if result.company_semantics else {},
            "final_direction": result.final_direction,
        },
    }


def _mapped_directions(values: list[str]) -> list[str]:
    return [PREMATCH_TO_OUTCOME[value] for value in values if value in PREMATCH_TO_OUTCOME]


def build_prematch_snapshot(loaded: LoadedInput, result: Any) -> PrematchSnapshot:
    """Project a completed pre-match pipeline run into the shared snapshot schema."""

    if result.stop or not result.final_direction:
        raise ValueError(f"pre-match pipeline did not produce a snapshot: {result.stop_reason or 'final direction missing'}")
    final_direction = PREMATCH_TO_OUTCOME.get(result.final_direction)
    if final_direction is None:
        raise ValueError(f"unsupported final direction: {result.final_direction}")
    score_range, margin_targets = _score_defaults(final_direction)
    structural_lean = PREMATCH_TO_OUTCOME.get(result.structural_lean) if result.structural_lean else None
    strength = result.strength_context or loaded.strength
    expected = result.interval_audit.expected if result.interval_audit else None
    distribution = asdict(result.original_distribution) if result.original_distribution else {}
    company_alignment = result.company_semantics.relation_type if result.company_semantics else None
    source_files = list(loaded.source_files) or ["canonical_input"]
    evidence_gaps = list(result.missing_fields)
    if result.narrative_audit and result.narrative_audit.review_required:
        evidence_gaps.append("三项题材来源级审计不完整")
    if result.skeleton_scope_status != "HOME_AXIS_PRECISE":
        evidence_gaps.append("当前赔率形态超出主赔精确轴，平赔或客赔只能作为组合参考")
    snapshot = PrematchSnapshot.from_dict(
        {
            "schema_version": "0.2",
            "match_id": _match_id(loaded),
            "competition": loaded.match.competition,
            "home_team": loaded.match.home_team,
            "away_team": loaded.match.away_team,
            "match_time": loaded.match.kickoff_time,
            "neutral_ground": loaded.match.neutral_venue,
            "source_type": "focas_prematch_pipeline",
            "source_files": source_files,
            "basic_face_complete": result.basic_context_status == "COMPLETE",
            "basic_face_gaps": list(result.missing_fields),
            "home_strength_grade": strength.home_grade or "未知",
            "away_strength_grade": strength.away_grade or "未知",
            "strength_diff": strength.final_gap or strength.static_gap or "未知",
            "dynamic_revision": strength.dynamic_adjustment,
            "theoretical_system": getattr(expected, "source", None),
            "theoretical_interval": getattr(expected, "expected_interval", None)
            or strength.theoretical_psychological_interval
            or "未知",
            "theoretical_interval_source": getattr(expected, "expected_interval_source", None),
            "actual_opening_interval": _interval_coordinates(loaded, result, "initial"),
            "actual_latest_interval": _interval_coordinates(loaded, result, "current"),
            "opening_deviation": _opening_deviation(result),
            "odds_move_deviation": _movement_deviation(result),
            "original_distribution": distribution,
            "company_motive_chain": _company_motive_chain(result),
            "unfavorable_directions": _mapped_directions(
                list(result.integrated_structure.adverse_excluded_directions) if result.integrated_structure else []
            ),
            "unfavorable_score_patterns": [],
            "relative_mainline_selection": structural_lean or final_direction,
            "final_direction": final_direction,
            "score_range": score_range,
            "margin_targets": margin_targets,
            "evidence_gaps": evidence_gaps,
            "companies": list(_odds_coordinates(loaded, "initial")),
            "opening": _odds_coordinates(loaded, "initial"),
            "latest_or_closing": _odds_coordinates(loaded, "current"),
            "final": None,
            "odds_pattern_tags": [f"{item.company}:{item.direction}:{item.action}" for item in result.odds_moves],
            "company_alignment": company_alignment,
            "pre_match_summary": (
                f"FOCAS 赛前决策状态={result.decision_status}；结构方向={final_direction}；"
                f"实力差={strength.final_gap or strength.static_gap or '未知'}；"
                f"理论区间={getattr(expected, 'expected_interval', None) or '未知'}。"
            ),
            "decision_status": result.decision_status,
            "structural_lean": structural_lean,
            "narrative_audit": asdict(result.narrative_audit) if result.narrative_audit else {},
            "scenario_audit": asdict(result.scenario_audit) if result.scenario_audit else {},
        }
    )
    return snapshot


def analyze_match_package(
    match_package: str | Path,
    *,
    out: str | Path | None = None,
    fingerprint_out: str | Path | None = None,
    experience_out: str | Path | None = None,
    with_experience: bool = False,
    table_path: str | Path | None = None,
) -> PrematchSnapshot:
    """Analyze an input package and optionally write snapshot and fingerprint JSON."""

    loaded = load_input_with_report(match_package)
    match, strength, pulls, book_mode, odds = loaded.as_tuple()
    pipeline = FocasPipeline(table_path=str(table_path or DEFAULT_TABLE_PATH))
    result = pipeline.run(
        match=match,
        strength=strength,
        pulls=pulls,
        narrative_materials=loaded.narrative_materials,
        book_mode=book_mode,
        odds=odds,
    )
    snapshot = build_prematch_snapshot(loaded, result)
    fingerprint = build_fingerprint(snapshot)
    if out:
        _json_write(Path(out), snapshot.to_dict())
    if fingerprint_out:
        _json_write(Path(fingerprint_out), fingerprint)
    if with_experience:
        from focas_experience.report import build_experience_report

        report = build_experience_report(fingerprint)
        _json_write(Path(experience_out or "experience_report.json"), report)
    return snapshot
