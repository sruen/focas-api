"""Statistics and strict promotion checks for post-match fact samples."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable

from shared.postmatch_schema import PostmatchSample
from .store import all_samples, find_similar, update_sample


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _direction_hit_rate(samples: Iterable[PostmatchSample]) -> dict[str, int | float | None]:
    sample_list = list(samples)
    hits = sum(sample.validation.direction_hit for sample in sample_list)
    return {"total": len(sample_list), "hits": hits, "hit_rate": _rate(hits, len(sample_list))}


def _group_by_value(
    samples: list[PostmatchSample], value_getter: Callable[[PostmatchSample], str | None]
) -> dict[str, dict[str, int | float | None]]:
    groups: dict[str, list[PostmatchSample]] = {}
    for sample in samples:
        value = value_getter(sample)
        if value:
            groups.setdefault(value, []).append(sample)
    return {name: _direction_hit_rate(group) for name, group in sorted(groups.items())}


def _group_by_tags(samples: list[PostmatchSample], attribute: str) -> dict[str, dict[str, int | float | None]]:
    groups: dict[str, list[PostmatchSample]] = {}
    for sample in samples:
        for value in dict.fromkeys(getattr(sample.tags, attribute)):
            groups.setdefault(value, []).append(sample)
    return {name: _direction_hit_rate(group) for name, group in sorted(groups.items())}


def is_counterexample(sample: PostmatchSample) -> bool:
    """Return whether a sample is a counterexample for promotion statistics."""

    return (
        not sample.validation.direction_hit
        or sample.validation.logic_hit is False
        or sample.promotion.status == "rejected"
        or "错因" in sample.error_or_success.primary_type
        or bool(sample.tags.error_tags)
    )


def summary() -> dict[str, Any]:
    """Return aggregate post-match fact sample statistics."""

    samples = all_samples()
    total = len(samples)
    direction_hits = sum(sample.validation.direction_hit for sample in samples)
    score_range_hits = sum(sample.validation.score_range_hit for sample in samples)
    margin_hits = sum(sample.validation.margin_hit for sample in samples)
    logic_samples = [sample for sample in samples if sample.validation.logic_hit is not None]
    logic_hits = sum(bool(sample.validation.logic_hit) for sample in logic_samples)
    counterexamples = sum(is_counterexample(sample) for sample in samples)
    by_error_tags = dict(sorted(Counter(tag for sample in samples for tag in sample.tags.error_tags).items()))
    rule_candidates = [
        {
            "sample_id": sample.sample_id,
            "similar_sample_key": sample.promotion.similar_sample_key,
            "similar_sample_count": sample.promotion.similar_sample_count,
            "candidate_rule": sample.lesson.candidate_rule,
        }
        for sample in samples
        if sample.promotion.status == "rule_candidate"
    ]
    return {
        "total_samples": total,
        "direction_hit_rate": _rate(direction_hits, total),
        "score_range_hit_rate": _rate(score_range_hits, total),
        "margin_hit_rate": _rate(margin_hits, total),
        "logic_hit_rate": _rate(logic_hits, len(logic_samples)),
        "logic_hit_sample_count": len(logic_samples),
        "counterexample_rate": _rate(counterexamples, total),
        "by_strength_diff": _group_by_value(samples, lambda sample: sample.pre_match_structure.strength_diff),
        "by_theoretical_interval": _group_by_value(
            samples, lambda sample: sample.pre_match_structure.theoretical_interval
        ),
        "by_final_direction": _group_by_value(samples, lambda sample: sample.pre_match.final_direction),
        "by_actual_outcome": _group_by_value(samples, lambda sample: sample.result.outcome),
        "by_company_alignment": _group_by_value(samples, lambda sample: sample.odds.company_alignment),
        "by_odds_tags": _group_by_tags(samples, "odds_tags"),
        "by_error_tags": by_error_tags,
        # Retained aliases for existing v0.1 consumers.
        "by_structure_tags": _group_by_tags(samples, "structure_tags"),
        "error_tags": by_error_tags,
        "by_company_tags": _group_by_tags(samples, "company_tags"),
        "rule_candidates": rule_candidates,
    }


def _append_blocked(blocked: list[str], condition: bool, message: str) -> None:
    if not condition:
        blocked.append(message)


def promotion_check(similar_sample_key: str) -> dict[str, Any]:
    """Update sample-library statuses without modifying any pre-match rules."""

    samples = find_similar(similar_sample_key)
    count = len(samples)
    direction_hit_rate = _rate(sum(sample.validation.direction_hit for sample in samples), count)
    logic_samples = [sample for sample in samples if sample.validation.logic_hit is not None]
    logic_hit_rate = _rate(sum(sample.validation.logic_hit is True for sample in logic_samples), len(logic_samples))
    counterexample_rate = _rate(sum(is_counterexample(sample) for sample in samples), count)
    structures_complete = bool(samples) and all(sample.pre_match_structure.core_fields_complete() for sample in samples)
    competitions = {sample.match.competition for sample in samples if sample.match.competition}
    source_types = {sample.source_type for sample in samples if sample.source_type}
    diverse_environments = len(competitions) >= 2 or len(source_types) >= 2
    direction_rate = direction_hit_rate or 0.0
    logic_rate = logic_hit_rate if logic_hit_rate is not None else 0.0
    counterexample = counterexample_rate or 0.0

    watch_ok = count >= 3 and direction_rate >= 0.50
    usable_ok = (
        count >= 5
        and direction_rate >= 0.60
        and bool(logic_samples)
        and logic_rate >= 0.60
        and counterexample <= 0.40
        and structures_complete
    )
    rule_candidate_ok = (
        count >= 10
        and direction_rate >= 0.65
        and bool(logic_samples)
        and logic_rate >= 0.65
        and counterexample <= 0.25
        and structures_complete
        and diverse_environments
    )
    if rule_candidate_ok:
        status = "rule_candidate"
    elif usable_ok:
        status = "usable"
    elif watch_ok:
        status = "watch"
    else:
        status = "candidate"

    blocked_reasons: list[str] = []
    if count < 3:
        blocked_reasons.append("同类样本少于 3 场，只能保留为 candidate。")
    elif not watch_ok:
        blocked_reasons.append("方向命中率低于 0.50，不能进入 watch。")
    if count >= 5 and not usable_ok:
        _append_blocked(blocked_reasons, direction_rate >= 0.60, "方向命中率低于 usable 门槛 0.60。")
        _append_blocked(blocked_reasons, bool(logic_samples), "缺少可计算 logic_hit_rate 的样本。")
        _append_blocked(blocked_reasons, logic_rate >= 0.60, "logic_hit_rate 低于 usable 门槛 0.60。")
        _append_blocked(blocked_reasons, counterexample <= 0.40, "反例率高于 usable 上限 0.40。")
        _append_blocked(blocked_reasons, structures_complete, "pre_match_structure 核心字段不完整。")
    if count >= 10 and not rule_candidate_ok:
        _append_blocked(blocked_reasons, direction_rate >= 0.65, "方向命中率低于规则候选门槛 0.65。")
        _append_blocked(blocked_reasons, bool(logic_samples), "缺少可计算 logic_hit_rate 的样本。")
        _append_blocked(blocked_reasons, logic_rate >= 0.65, "logic_hit_rate 低于规则候选门槛 0.65。")
        _append_blocked(blocked_reasons, counterexample <= 0.25, "反例率高于规则候选上限 0.25。")
        _append_blocked(blocked_reasons, structures_complete, "pre_match_structure 核心字段不完整。")
        _append_blocked(blocked_reasons, diverse_environments, "缺少至少 2 个 competition 或 source_type 环境。")

    if status == "rule_candidate":
        reason = "满足严格门槛，仅标记为规则候选；不会自动修改 FOCAS 赛前规则。"
    else:
        reason = f"同类样本共 {count} 场，按数量、命中率、反例率和结构完整性标记为 {status}。"
    updated_sample_ids: list[str] = []
    for sample in samples:
        if sample.promotion.status == "rejected":
            continue
        update_sample(
            sample.sample_id,
            {
                "promotion": {
                    "status": status,
                    "similar_sample_count": count,
                    "promotion_reason": reason,
                }
            },
        )
        updated_sample_ids.append(sample.sample_id)
    return {
        "similar_sample_key": similar_sample_key,
        "count": count,
        "similar_sample_count": count,
        "status": status,
        "direction_hit_rate": direction_hit_rate,
        "logic_hit_rate": logic_hit_rate,
        "counterexample_rate": counterexample_rate,
        "updated_sample_ids": updated_sample_ids,
        "promotion_reason": reason,
        "blocked_reasons": blocked_reasons,
    }
