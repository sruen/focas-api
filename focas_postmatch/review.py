"""Generate a validated post-match sample from immutable pre-match facts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.fingerprint import build_fingerprint
from shared.postmatch_schema import PostmatchSample
from shared.prematch_schema import PrematchSnapshot
from shared.result_schema import ResultPayload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validation_summary(snapshot: PrematchSnapshot, result: dict[str, Any], validation: dict[str, Any]) -> str:
    parts = [
        f"方向{'命中' if validation['direction_hit'] else '未命中'}",
        f"比分区间{'命中' if validation['score_range_hit'] else '未命中'}",
    ]
    if snapshot.margin_targets:
        parts.append(f"幅度{'命中' if validation['margin_hit'] else '未命中'}")
    else:
        parts.append("赛前未提供 margin_targets，无法验证幅度")
    return "；".join(parts) + f"。实际比分={result['final_score']}。"


def _default_three_way_review(result: dict[str, Any]) -> dict[str, str]:
    outcome = result["outcome"]
    return {
        "win_review": f"实际赛果={outcome}，主胜路径按赛前快照复盘。",
        "draw_review": f"实际赛果={outcome}，平局路径按赛前快照复盘。",
        "loss_review": f"实际赛果={outcome}，客胜路径按赛前快照复盘。",
    }


def _default_logic_audit(snapshot: PrematchSnapshot) -> dict[str, Any]:
    return {
        "basic_face_validated": None,
        "strength_grade_validated": None,
        "original_distribution_validated": None,
        "opening_odds_validated": snapshot.opening_deviation,
        "odds_move_validated": snapshot.odds_move_deviation,
        "flat_odds_validated": None,
        "company_motive_validated": snapshot.company_alignment,
        "trading_volume_validated": None,
        "special_variables": [],
    }


def _default_error_or_success(validation: dict[str, Any]) -> dict[str, Any]:
    if validation["direction_hit"]:
        return {
            "primary_type": "方向命中",
            "secondary_types": [],
            "explanation": "方向命中；比分区间和幅度命中情况由 validation 字段自动记录。",
        }
    return {
        "primary_type": "错因：方向未命中",
        "secondary_types": [],
        "explanation": "实际结果与赛前方向不一致，需要人工补充错因审计。",
    }


def build_postmatch_sample(
    snapshot: PrematchSnapshot,
    result_payload: ResultPayload,
    *,
    source_files: list[str] | None = None,
) -> PostmatchSample:
    """Build and validate one v0.2 sample without rewriting pre-match rules."""

    result = result_payload.factual_result()
    validation = {
        "direction_hit": snapshot.final_direction == result["outcome"],
        "score_range_hit": result["final_score"] in snapshot.score_range,
        "margin_hit": bool(snapshot.margin_targets) and abs(result["goal_margin"]) in snapshot.margin_targets,
        "logic_hit": result_payload.logic_hit,
        "process_risk_covered": result_payload.process_risk_covered,
        "validation_summary": result_payload.validation_summary or "",
    }
    if not validation["validation_summary"]:
        validation["validation_summary"] = _validation_summary(snapshot, result, validation)
    review = result_payload.review
    default_error = _default_error_or_success(validation)
    tags = review.get("tags", {})
    error_tags = list(tags.get("error_tags", []))
    if not validation["direction_hit"] and "方向未命中" not in error_tags:
        error_tags.append("方向未命中")
    fingerprint = build_fingerprint(snapshot)
    similar_sample_key = fingerprint["similar_sample_key"]
    now = _now_iso()
    sample = PostmatchSample.from_dict(
        {
            "schema_version": "0.2",
            "sample_id": "",
            "match_id": snapshot.match_id,
            "created_at": now,
            "updated_at": now,
            "source_type": "prematch_snapshot+result",
            "source_files": list(source_files or []),
            "distribution_fingerprint": fingerprint["distribution_fingerprint"],
            "interval_fingerprint": fingerprint["interval_fingerprint"],
            "movement_fingerprint": fingerprint["movement_fingerprint"],
            "structure_key_coarse": fingerprint["structure_key_coarse"],
            "structure_key_exact": fingerprint["structure_key_exact"],
            "movement_key": fingerprint["movement_key"],
            "decision_key": fingerprint["decision_key"],
            "match": {
                "home_team": snapshot.home_team,
                "away_team": snapshot.away_team,
                "competition": snapshot.competition,
                "match_date": snapshot.match_time,
                "neutral_ground": snapshot.neutral_ground,
            },
            "pre_match": {
                "final_direction": snapshot.final_direction,
                "score_range": list(snapshot.score_range),
                "margin_targets": list(snapshot.margin_targets),
                "margin_view": review.get("margin_view"),
                "pre_match_summary": snapshot.pre_match_summary,
            },
            "pre_match_structure": {
                "basic_face_complete": snapshot.basic_face_complete,
                "basic_face_gaps": list(snapshot.basic_face_gaps),
                "home_strength_grade": snapshot.home_strength_grade,
                "away_strength_grade": snapshot.away_strength_grade,
                "strength_diff": snapshot.strength_diff,
                "dynamic_revision": snapshot.dynamic_revision,
                "theoretical_system": snapshot.theoretical_system,
                "theoretical_interval": snapshot.theoretical_interval,
                "theoretical_interval_source": snapshot.theoretical_interval_source,
                "actual_opening_interval": snapshot.actual_opening_interval,
                "actual_latest_interval": snapshot.actual_latest_interval,
                "opening_deviation": snapshot.opening_deviation,
                "odds_move_deviation": snapshot.odds_move_deviation,
                "original_distribution": snapshot.original_distribution,
                "unfavorable_directions": list(snapshot.unfavorable_directions),
                "unfavorable_score_patterns": list(snapshot.unfavorable_score_patterns),
                "relative_mainline_selection": snapshot.relative_mainline_selection,
                "company_motive_chain": snapshot.company_motive_chain,
                "evidence_gaps": list(snapshot.evidence_gaps),
                "decision_status": snapshot.decision_status,
                "structural_lean": snapshot.structural_lean,
                "narrative_audit": snapshot.narrative_audit,
                "scenario_audit": snapshot.scenario_audit,
            },
            "odds": {
                "companies": list(snapshot.companies),
                "opening": snapshot.opening,
                "latest_or_closing": snapshot.latest_or_closing,
                "final": snapshot.final,
                "odds_pattern_tags": list(snapshot.odds_pattern_tags),
                "company_alignment": snapshot.company_alignment,
            },
            "result": result,
            "validation": validation,
            "three_way_review": review.get("three_way_review", _default_three_way_review(result)),
            "logic_audit": review.get("logic_audit", _default_logic_audit(snapshot)),
            "error_or_success": review.get("error_or_success", default_error),
            "tags": {
                "structure_tags": list(
                    tags.get(
                        "structure_tags",
                        [snapshot.strength_diff, snapshot.theoretical_interval, snapshot.relative_mainline_selection],
                    )
                ),
                "error_tags": error_tags,
                "company_tags": list(tags.get("company_tags", [snapshot.company_alignment] if snapshot.company_alignment else [])),
                "odds_tags": list(tags.get("odds_tags", snapshot.odds_pattern_tags)),
            },
            "lesson": review.get(
                "lesson",
                {
                    "reusable_pattern": None,
                    "candidate_rule": None,
                    "overfit_warning": "单场事实样本不能直接升级为规则。",
                    "next_time_questions": [],
                },
            ),
            "promotion": {
                "status": "candidate",
                "similar_sample_key": similar_sample_key,
                "similar_sample_count": 1,
                "promotion_reason": "新生成事实样本，只能保留为候选规律。",
            },
        }
    )
    sample.validate()
    return sample


def review_files(prematch: str | Path, result: str | Path, out: str | Path) -> PostmatchSample:
    """Read snapshot and result JSON, write a generated post-match sample JSON."""

    prematch_path = Path(prematch)
    result_path = Path(result)
    snapshot = PrematchSnapshot.from_dict(_json_read(prematch_path))
    payload = ResultPayload.from_dict(_json_read(result_path))
    sample = build_postmatch_sample(snapshot, payload, source_files=[str(prematch_path), str(result_path)])
    _json_write(Path(out), sample.to_dict())
    return sample
