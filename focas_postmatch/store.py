"""JSONL storage for independent post-match review samples."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from shared.postmatch_schema import PostmatchSample

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "postmatch"
DATA_DIR_ENV = "FOCAS_POSTMATCH_DATA_DIR"


def _data_dir() -> Path:
    return Path(os.environ.get(DATA_DIR_ENV, DEFAULT_DATA_DIR))


def _samples_path() -> Path:
    return _data_dir() / "postmatch_samples.jsonl"


def _index_path() -> Path:
    return _data_dir() / "postmatch_sample_index.json"


def _ensure_data_files() -> None:
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    samples_path = _samples_path()
    if not samples_path.exists():
        samples_path.write_text("", encoding="utf-8")
    index_path = _index_path()
    if not index_path.exists():
        _write_index([])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_sample_id() -> str:
    return f"PMS-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12]}"


def _read_samples() -> list[PostmatchSample]:
    _ensure_data_files()
    samples: list[PostmatchSample] = []
    with _samples_path().open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                samples.append(PostmatchSample.from_dict(data, require_sample_id=True))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid sample at JSONL line {line_number}: {exc}") from exc
    return samples


def _write_samples(samples: list[PostmatchSample]) -> None:
    _ensure_data_files()
    for sample in samples:
        sample.validate(require_sample_id=True)
    samples_path = _samples_path()
    temp_path = samples_path.with_suffix(".jsonl.tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        for sample in samples:
            handle.write(json.dumps(sample.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n")
    temp_path.replace(samples_path)
    _write_index(samples)


def _tag_values(sample: PostmatchSample) -> list[str]:
    return list(
        dict.fromkeys(
            sample.tags.structure_tags
            + sample.tags.error_tags
            + sample.tags.company_tags
            + sample.tags.odds_tags
        )
    )


def _append_index(index: dict[str, list[str]], key: str | None, sample_id: str) -> None:
    if key is not None and key != "":
        index.setdefault(key, []).append(sample_id)


def _write_index(samples: list[PostmatchSample]) -> dict[str, Any]:
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    by_match: dict[str, list[str]] = {}
    by_tag: dict[str, list[str]] = {}
    by_similar_sample_key: dict[str, list[str]] = {}
    by_structure_key_coarse: dict[str, list[str]] = {}
    by_structure_key_exact: dict[str, list[str]] = {}
    by_movement_key: dict[str, list[str]] = {}
    by_decision_key: dict[str, list[str]] = {}
    by_strength_diff: dict[str, list[str]] = {}
    by_theoretical_interval: dict[str, list[str]] = {}
    by_final_direction: dict[str, list[str]] = {}
    by_actual_outcome: dict[str, list[str]] = {}
    by_error_type: dict[str, list[str]] = {}
    by_company_alignment: dict[str, list[str]] = {}
    by_odds_pattern: dict[str, list[str]] = {}
    by_promotion_status: dict[str, list[str]] = {}
    items: dict[str, dict[str, Any]] = {}
    for sample in samples:
        match_key = f"{sample.match.home_team}::{sample.match.away_team}"
        _append_index(by_match, match_key, sample.sample_id)
        for tag in _tag_values(sample):
            _append_index(by_tag, tag, sample.sample_id)
        similar_key = sample.promotion.similar_sample_key
        _append_index(by_similar_sample_key, similar_key, sample.sample_id)
        _append_index(by_structure_key_coarse, sample.structure_key_coarse, sample.sample_id)
        _append_index(by_structure_key_exact, sample.structure_key_exact, sample.sample_id)
        _append_index(by_movement_key, sample.movement_key, sample.sample_id)
        _append_index(by_decision_key, sample.decision_key, sample.sample_id)
        _append_index(by_strength_diff, sample.pre_match_structure.strength_diff, sample.sample_id)
        _append_index(by_theoretical_interval, sample.pre_match_structure.theoretical_interval, sample.sample_id)
        _append_index(by_final_direction, sample.pre_match.final_direction, sample.sample_id)
        _append_index(by_actual_outcome, sample.result.outcome, sample.sample_id)
        _append_index(by_error_type, sample.error_or_success.primary_type, sample.sample_id)
        _append_index(by_company_alignment, sample.odds.company_alignment, sample.sample_id)
        for pattern in dict.fromkeys(sample.odds.odds_pattern_tags + sample.tags.odds_tags):
            _append_index(by_odds_pattern, pattern, sample.sample_id)
        _append_index(by_promotion_status, sample.promotion.status, sample.sample_id)
        items[sample.sample_id] = {
            "match_id": sample.match_id,
            "home_team": sample.match.home_team,
            "away_team": sample.match.away_team,
            "competition": sample.match.competition,
            "final_score": sample.result.final_score,
            "pre_match_direction": sample.pre_match.final_direction,
            "final_direction": sample.pre_match.final_direction,
            "actual_outcome": sample.result.outcome,
            "direction_hit": sample.validation.direction_hit,
            "logic_hit": sample.validation.logic_hit,
            "home_strength_grade": sample.pre_match_structure.home_strength_grade,
            "away_strength_grade": sample.pre_match_structure.away_strength_grade,
            "strength_diff": sample.pre_match_structure.strength_diff,
            "theoretical_interval": sample.pre_match_structure.theoretical_interval,
            "promotion_status": sample.promotion.status,
            "similar_sample_key": similar_key,
            "structure_key_coarse": sample.structure_key_coarse,
            "structure_key_exact": sample.structure_key_exact,
            "movement_key": sample.movement_key,
            "decision_key": sample.decision_key,
        }
    index = {
        "updated_at": _now_iso(),
        "total_samples": len(samples),
        "samples": items,
        "by_match": by_match,
        "by_tag": by_tag,
        "by_similar_sample_key": by_similar_sample_key,
        "by_structure_key_coarse": by_structure_key_coarse,
        "by_structure_key_exact": by_structure_key_exact,
        "by_movement_key": by_movement_key,
        "by_decision_key": by_decision_key,
        "by_strength_diff": by_strength_diff,
        "by_theoretical_interval": by_theoretical_interval,
        "by_final_direction": by_final_direction,
        "by_actual_outcome": by_actual_outcome,
        "by_error_type": by_error_type,
        "by_company_alignment": by_company_alignment,
        "by_odds_pattern": by_odds_pattern,
        "by_promotion_status": by_promotion_status,
    }
    _index_path().write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def rebuild_index() -> dict[str, Any]:
    """Rebuild and return the searchable index from JSONL storage."""

    return _write_index(_read_samples())


def _is_duplicate(existing: PostmatchSample, incoming: PostmatchSample) -> bool:
    return (
        incoming.match_id is not None
        and existing.match_id == incoming.match_id
        and existing.result.final_score == incoming.result.final_score
        and existing.pre_match.final_direction == incoming.pre_match.final_direction
    )


def add_sample(sample: PostmatchSample) -> str:
    """Add a validated sample and return its id.

    Duplicate additions are idempotent: the existing id is returned when
    match_id, final_score, and final_direction are all equal.
    """

    samples = _read_samples()
    incoming = PostmatchSample.from_dict(sample.to_dict())
    for existing in samples:
        if _is_duplicate(existing, incoming):
            return existing.sample_id
    now = _now_iso()
    incoming.sample_id = incoming.sample_id.strip() or _new_sample_id()
    if any(existing.sample_id == incoming.sample_id for existing in samples):
        raise ValueError(f"sample_id already exists: {incoming.sample_id}")
    incoming.created_at = incoming.created_at or now
    incoming.updated_at = now
    incoming.validate(require_sample_id=True)
    samples.append(incoming)
    _write_samples(samples)
    return incoming.sample_id


def get_sample(sample_id: str) -> PostmatchSample | None:
    """Return one sample by id."""

    return next((sample for sample in _read_samples() if sample.sample_id == sample_id), None)


def list_samples(limit: int = 50) -> list[PostmatchSample]:
    """Return the most recently stored samples first."""

    if limit < 0:
        raise ValueError("limit must be >= 0")
    samples = _read_samples()
    if limit == 0:
        return []
    return list(reversed(samples[-limit:]))


def all_samples() -> list[PostmatchSample]:
    """Return every stored sample in storage order."""

    return _read_samples()


def find_by_match(home_team: str, away_team: str) -> list[PostmatchSample]:
    """Return samples matching the exact home and away team names."""

    return [
        sample
        for sample in _read_samples()
        if sample.match.home_team == home_team and sample.match.away_team == away_team
    ]


def find_by_tags(tags: list[str]) -> list[PostmatchSample]:
    """Return samples containing all requested tags."""

    requested = set(tags)
    if not requested:
        return []
    return [sample for sample in _read_samples() if requested.issubset(set(_tag_values(sample)))]


def find_similar(similar_sample_key: str) -> list[PostmatchSample]:
    """Return samples with an equal similar-sample key."""

    return [
        sample
        for sample in _read_samples()
        if sample.promotion.similar_sample_key == similar_sample_key
    ]


def _deep_merge(original: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(original)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def update_sample(sample_id: str, patch: dict[str, Any]) -> PostmatchSample:
    """Apply a validated partial patch to a stored sample."""

    if not isinstance(patch, dict):
        raise ValueError("patch must be a dict")
    samples = _read_samples()
    for index, sample in enumerate(samples):
        if sample.sample_id != sample_id:
            continue
        merged = _deep_merge(sample.to_dict(), patch)
        merged["sample_id"] = sample_id
        merged["created_at"] = sample.created_at
        merged["updated_at"] = _now_iso()
        updated = PostmatchSample.from_dict(merged, require_sample_id=True)
        for other in samples:
            if other.sample_id != sample_id and _is_duplicate(other, updated):
                raise ValueError("patch would create a duplicate sample")
        samples[index] = updated
        _write_samples(samples)
        return updated
    raise KeyError(f"sample not found: {sample_id}")


def delete_sample(sample_id: str) -> bool:
    """Delete a sample and rebuild the index."""

    samples = _read_samples()
    remaining = [sample for sample in samples if sample.sample_id != sample_id]
    if len(remaining) == len(samples):
        return False
    _write_samples(remaining)
    return True
