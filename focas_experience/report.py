"""Read-only historical experience reports."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from focas_postmatch.analyzer import is_counterexample
from focas_postmatch.store import all_samples
from shared.fingerprint import validate_fingerprint
from shared.postmatch_schema import PostmatchSample


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _top(counter: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    return [{"pattern": pattern, "count": count} for pattern, count in counter.most_common(limit)]


def _sample_ids(samples: list[PostmatchSample]) -> list[str]:
    return [sample.sample_id for sample in samples]


def _fingerprint_complete(fingerprint: dict[str, Any]) -> bool:
    distribution = fingerprint.get("distribution_fingerprint")
    interval = fingerprint.get("interval_fingerprint")
    movement = fingerprint.get("movement_fingerprint")
    if not all(isinstance(value, dict) and value for value in (distribution, interval, movement)):
        return False
    if set(distribution.get("market_pull_map", {})) != {"win", "draw", "loss"}:
        return False
    if distribution.get("original_distribution_type") in {None, "", "未确认"}:
        return False
    if not isinstance(interval.get("actual_opening_interval"), dict) or not interval["actual_opening_interval"]:
        return False
    if interval.get("theoretical_system") in {None, "", "未知"}:
        return False
    if interval.get("theoretical_interval") in {None, "", "未知"}:
        return False
    required_keys = ("structure_key_coarse", "structure_key_exact", "movement_key", "decision_key")
    return all(isinstance(fingerprint.get(key), str) and fingerprint[key] for key in required_keys)


def _weak_score(sample: PostmatchSample, fingerprint: dict[str, Any]) -> int:
    score = 0
    if fingerprint.get("strength_diff") and sample.pre_match_structure.strength_diff == fingerprint["strength_diff"]:
        score += 1
    if (
        fingerprint.get("theoretical_interval")
        and sample.pre_match_structure.theoretical_interval == fingerprint["theoretical_interval"]
    ):
        score += 1
    if fingerprint.get("movement_key") and sample.movement_key == fingerprint["movement_key"]:
        score += 1
    return score


def _match_sets(samples: list[PostmatchSample], fingerprint: dict[str, Any]) -> dict[str, list[PostmatchSample]]:
    coarse_key = fingerprint.get("structure_key_coarse")
    exact_key = fingerprint.get("structure_key_exact")
    movement_key = fingerprint.get("movement_key")
    decision_key = fingerprint.get("decision_key")
    distribution = [sample for sample in samples if coarse_key and sample.structure_key_coarse == coarse_key]
    exact = [sample for sample in distribution if exact_key and sample.structure_key_exact == exact_key]
    movement = [sample for sample in exact if movement_key and sample.movement_key == movement_key]
    decisions = [sample for sample in samples if decision_key and sample.decision_key == decision_key]
    weak = [
        sample
        for sample in samples
        if sample not in distribution and _weak_score(sample, fingerprint) >= 1
    ]
    return {
        "distribution_matches": distribution,
        "exact_interval_matches": exact,
        "movement_matches": movement,
        "decision_matches": decisions,
        "weak_matches": weak,
    }


def _statistics(samples: list[PostmatchSample]) -> dict[str, float | None]:
    logic_samples = [sample for sample in samples if sample.validation.logic_hit is not None]
    return {
        "direction_hit_rate": _rate(sum(sample.validation.direction_hit for sample in samples), len(samples)),
        "logic_hit_rate": _rate(sum(sample.validation.logic_hit is True for sample in logic_samples), len(logic_samples)),
        "counterexample_rate": _rate(sum(is_counterexample(sample) for sample in samples), len(samples)),
    }


def _experience_level(
    *,
    distribution_sample_count: int | None = None,
    exact_interval_sample_count: int | None = None,
    direction_hit_rate: float | None,
    logic_hit_rate: float | None,
    counterexample_rate: float | None,
    fingerprint_complete: bool = True,
    count: int | None = None,
) -> str:
    """Return the experience level using exact intervals for A and distributions for B."""

    distribution_count = distribution_sample_count if distribution_sample_count is not None else (count or 0)
    exact_count = exact_interval_sample_count if exact_interval_sample_count is not None else (count or 0)
    if not fingerprint_complete or distribution_count == 0:
        return "D"
    direction = direction_hit_rate or 0.0
    logic = logic_hit_rate or 0.0
    counterexamples = counterexample_rate if counterexample_rate is not None else 1.0
    if (
        exact_count >= 5
        and direction >= 0.60
        and logic_hit_rate is not None
        and logic >= 0.60
        and counterexamples <= 0.40
    ):
        return "A"
    if distribution_count >= 5 and exact_count < 5:
        return "B"
    return "C"


def _mainline_effect(level: str) -> str:
    if level == "A":
        return "可作为 P8 第二阶段相对主线选择的辅助证据；不得单独决定最终方向。"
    if level == "B":
        return "原始分布同类样本只能提示风险；不得参与最终方向决策。"
    if level == "C":
        return "只展示原始分布同类历史样本；不得进入赛前判断。"
    return "无完整同类分布经验，不进入赛前判断。"


def _counterexample_summary(samples: list[PostmatchSample]) -> list[dict[str, Any]]:
    reasons: Counter[str] = Counter()
    for sample in samples:
        if not sample.validation.direction_hit:
            reasons["方向未命中"] += 1
        if sample.validation.logic_hit is False:
            reasons["逻辑链未命中"] += 1
        if sample.validation.direction_hit and not sample.validation.score_range_hit:
            reasons["方向命中但比分区间未命中"] += 1
        if sample.validation.direction_hit and not sample.validation.margin_hit:
            reasons["方向命中但幅度未命中"] += 1
        if sample.tags.error_tags:
            reasons.update(sample.tags.error_tags)
        if "错因" in sample.error_or_success.primary_type:
            reasons[sample.error_or_success.primary_type] += 1
    return _top(reasons)


def _distribution(samples: list[PostmatchSample], getter: Any) -> dict[str, int]:
    return dict(Counter(getter(sample) for sample in samples).most_common())


def build_experience_report(fingerprint: dict[str, Any]) -> dict[str, Any]:
    """Build a layered report from historical samples only."""

    fingerprint = validate_fingerprint(fingerprint)
    complete = _fingerprint_complete(fingerprint)
    match_sets = _match_sets(all_samples(), fingerprint)
    distribution_matches = match_sets["distribution_matches"]
    exact_matches = match_sets["exact_interval_matches"]
    movement_matches = match_sets["movement_matches"]
    decision_matches = match_sets["decision_matches"]
    weak_matches = match_sets["weak_matches"]
    if movement_matches:
        matched_by = "movement_key"
    elif exact_matches:
        matched_by = "structure_key_exact"
    elif distribution_matches:
        matched_by = "structure_key_coarse"
    elif weak_matches:
        matched_by = "weak_fields"
    else:
        matched_by = "none"
    primary_samples = exact_matches or distribution_matches or weak_matches
    exact_statistics = _statistics(exact_matches)
    distribution_statistics = _statistics(distribution_matches)
    primary_statistics = exact_statistics if exact_matches else distribution_statistics
    if not distribution_matches:
        primary_statistics = _statistics(primary_samples)
    decision_statistics = _statistics(decision_matches)
    level = _experience_level(
        distribution_sample_count=len(distribution_matches),
        exact_interval_sample_count=len(exact_matches),
        direction_hit_rate=exact_statistics["direction_hit_rate"],
        logic_hit_rate=exact_statistics["logic_hit_rate"],
        counterexample_rate=exact_statistics["counterexample_rate"],
        fingerprint_complete=complete,
    )
    support = Counter(
        tag for sample in primary_samples if not is_counterexample(sample) for tag in sample.tags.structure_tags
    )
    risks = Counter(
        tag
        for sample in primary_samples
        if is_counterexample(sample)
        for tag in ([sample.error_or_success.primary_type] + sample.tags.error_tags)
    )
    common_errors = Counter(tag for sample in primary_samples for tag in sample.tags.error_tags)
    common_success = Counter(
        tag
        for sample in primary_samples
        if sample.validation.direction_hit and sample.validation.logic_hit is not False
        for tag in sample.tags.structure_tags
    )
    actual_scores = Counter(sample.result.final_score for sample in primary_samples)
    return {
        "experience_level": level,
        "usable_for_mainline": level == "A",
        "matched_by": matched_by,
        "fingerprint_complete": complete,
        "sample_count": len(primary_samples),
        "distribution_sample_count": len(distribution_matches),
        "exact_interval_sample_count": len(exact_matches),
        "movement_sample_count": len(movement_matches),
        "decision_sample_count": len(decision_matches),
        "direction_hit_rate": primary_statistics["direction_hit_rate"],
        "logic_hit_rate": primary_statistics["logic_hit_rate"],
        "counterexample_rate": primary_statistics["counterexample_rate"],
        "decision_hit_rate": decision_statistics["direction_hit_rate"],
        "distribution_matches": _sample_ids(distribution_matches),
        "exact_interval_matches": _sample_ids(exact_matches),
        "movement_matches": _sample_ids(movement_matches),
        "decision_matches": _sample_ids(decision_matches),
        "weak_matches": _sample_ids(weak_matches),
        "distribution_outcome_distribution": _distribution(distribution_matches, lambda sample: sample.result.outcome),
        "exact_interval_outcome_distribution": _distribution(exact_matches, lambda sample: sample.result.outcome),
        "outcome_distribution": _distribution(primary_samples, lambda sample: sample.result.outcome),
        "prematch_direction_distribution": _distribution(
            primary_samples, lambda sample: sample.pre_match.final_direction
        ),
        "main_distribution_risks": _counterexample_summary(distribution_matches),
        "main_interval_risks": _counterexample_summary(exact_matches),
        "main_movement_risks": _counterexample_summary(movement_matches),
        "main_counterexamples": _counterexample_summary(primary_samples),
        "supporting_patterns": _top(support),
        "risk_patterns": _top(risks),
        "common_error_tags": _top(common_errors),
        "common_success_tags": _top(common_success),
        "mainline_effect": _mainline_effect(level),
        "score_pattern_effect": {
            "actual_scores": dict(actual_scores.most_common()),
            "direction_hit_but_score_range_miss": sum(
                sample.validation.direction_hit and not sample.validation.score_range_hit for sample in primary_samples
            ),
            "direction_hit_but_margin_miss": sum(
                sample.validation.direction_hit and not sample.validation.margin_hit for sample in primary_samples
            ),
            "explanation": "展示历史比分形态和方向正确但比分或幅度错误的次数，不单独决定当前比赛方向。",
        },
        # v1.1.1 report aliases retained for readers that have not migrated yet.
        "structure_sample_count": len(exact_matches),
        "exact_structure_matches": _sample_ids(exact_matches),
        "partial_matches": _sample_ids([sample for sample in distribution_matches if sample not in exact_matches]),
        "explanation": (
            "经验报告先按原始分布做粗匹配，再按理论区间和现实开赔坐标做精确匹配，"
            "最后用变赔路径确认。decision_key 只观察同决策历史表现，不作为主匹配入口。"
            "任何经验等级都不得单独决定最终方向；A级也只能辅助 P8 第二阶段相对主线选择。"
        ),
    }


def query_experience(fingerprint_path: str | Path, out: str | Path = "experience_report.json") -> dict[str, Any]:
    """Read a fingerprint JSON and write its historical experience report."""

    fingerprint = json.loads(Path(fingerprint_path).read_text(encoding="utf-8"))
    report = build_experience_report(fingerprint)
    output = Path(out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
