"""Shared historical-experience fingerprint helpers."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Iterable

from .prematch_schema import PrematchSnapshot
from .validators import SharedValidationError, require_dict

FORBIDDEN_CURRENT_RESULT_KEYS = {
    "result",
    "outcome",
    "final_score",
    "home_goals",
    "away_goals",
    "goal_margin",
    "direction_hit",
    "score_range_hit",
    "margin_hit",
}
OUTCOME_MAP = {"主胜": "胜", "平局": "平", "客胜": "负", "胜": "胜", "平": "平", "负": "负"}
PULL_VALUES = {"强", "中", "弱", "无"}
SIDE_VALUES = {"胜", "平", "负", "无"}
MOVE_VALUES = {"抬高", "拉低", "稳定", "无数据"}


def _stable_key(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _side(value: Any, *, default: str = "无") -> str:
    return OUTCOME_MAP.get(value, default)


def _pull(value: Any) -> str:
    return value if value in PULL_VALUES else "无"


def _ordered_sides(values: Iterable[str]) -> list[str]:
    unique = set(values)
    return [side for side in ("胜", "平", "负") if side in unique]


def _distribution_subtype(
    pulls: dict[str, str],
    confidence_bearing_side: str,
    dispersion_sides: list[str],
) -> str | None:
    strong = {side for side, pull in pulls.items() if pull == "强"}
    if strong == {"win", "draw"}:
        return "胜平合力"
    if strong == {"draw", "loss"}:
        return "平负合力"
    if strong == {"win", "loss"}:
        return "胜负双份"
    if strong == {"win", "draw", "loss"}:
        return "三项分散"
    labels = {
        ("胜", ("平",)): "主胜强拉力_平局分流",
        ("胜", ("负",)): "主胜强拉力_客胜分流",
        ("胜", ("平", "负")): "主胜强拉力_平负分流",
        ("负", ("平",)): "客胜强拉力_平局分流",
        ("负", ("胜", "平")): "客胜强拉力_胜平分流",
        ("平", ("胜", "负")): "平局强拉力_胜负分流",
    }
    return labels.get((confidence_bearing_side, tuple(_ordered_sides(dispersion_sides))))


def _confidence_bearing_side(pulls: dict[str, str]) -> str:
    ranked = {"无": 0, "弱": 1, "中": 2, "强": 3}
    highest = max((ranked[pull] for pull in pulls.values()), default=0)
    sides = [side for side, pull in pulls.items() if ranked[pull] == highest and highest > 0]
    if len(sides) != 1:
        return "无"
    return {"win": "胜", "draw": "平", "loss": "负"}[sides[0]]


def _explicit_receiving_marker(original: dict[str, Any], side: str) -> bool:
    """Return whether a weak side is explicitly marked as able to receive flow."""

    aliases = {
        "胜": ("胜", "主胜", "win", "home"),
        "平": ("平", "平局", "draw"),
        "负": ("负", "客胜", "loss", "away"),
    }[side]
    for field in ("easy_to_receive", "equivalent", "dispersion_available"):
        markers = original.get(field)
        if isinstance(markers, dict) and any(markers.get(alias) is True for alias in aliases):
            return True
    return False


def _dispersion_sides(
    original: dict[str, Any],
    pulls: dict[str, str],
    *,
    confidence_bearing_side: str,
    natural_heat_side: str,
) -> list[str]:
    eligible: list[str] = []
    for key, side in (("win", "胜"), ("draw", "平"), ("loss", "负")):
        if side in {confidence_bearing_side, natural_heat_side}:
            continue
        pull = pulls[key]
        if pull in {"中", "强"} or (pull == "弱" and _explicit_receiving_marker(original, side)):
            eligible.append(side)
    return eligible


def _bookmaker_problem(
    *,
    natural_heat_side: str,
    confidence_bearing_side: str,
    dispersion_sides: list[str],
) -> str:
    heat = natural_heat_side if natural_heat_side != "无" else "未确认方向"
    confidence = confidence_bearing_side if confidence_bearing_side != "无" else "未确认方向"
    dispersion = "、".join(dispersion_sides) if dispersion_sides else "暂无明确分流方向"
    return f"市场自然热度集中于{heat}，原始信心主要由{confidence}承载，机构需要处理受注并检验{dispersion}的分流能力。"


def build_distribution_fingerprint(snapshot: PrematchSnapshot) -> dict[str, Any]:
    """Map the pre-odds distribution layer without using decisions or odds moves."""

    original = snapshot.original_distribution
    pulls = {
        "win": _pull(original.get("home_pressure")),
        "draw": _pull(original.get("draw_pressure")),
        "loss": _pull(original.get("away_pressure")),
    }
    natural_heat_side = _side(original.get("first_eye_direction"))
    confidence_bearing_side = _confidence_bearing_side(pulls)
    dispersion_sides = _dispersion_sides(
        original,
        pulls,
        confidence_bearing_side=confidence_bearing_side,
        natural_heat_side=natural_heat_side,
    )
    danger_value = original.get("danger_side")
    danger_side = _side(danger_value) if danger_value is not None else natural_heat_side
    if danger_side == "无":
        danger_side = confidence_bearing_side
    return {
        "original_distribution_type": str(original.get("distribution_type") or "未确认"),
        "distribution_subtype": _distribution_subtype(pulls, confidence_bearing_side, dispersion_sides),
        "market_pull_map": pulls,
        "confidence_bearing_side": confidence_bearing_side,
        "natural_heat_side": natural_heat_side,
        "dispersion_sides": dispersion_sides,
        "danger_side": danger_side,
        "bookmaker_problem": _bookmaker_problem(
            natural_heat_side=natural_heat_side,
            confidence_bearing_side=confidence_bearing_side,
            dispersion_sides=dispersion_sides,
        ),
    }


def _opening_interval_relation(opening_deviation: str | None) -> str:
    text = opening_deviation or ""
    if "现实浅于理论" in text:
        return "现实浅于理论"
    if "现实深于理论" in text:
        return "现实深于理论"
    if "表内" in text:
        return "表内"
    return "不确定"


def _coordinate_summary(value: str) -> str:
    text = str(value).strip()
    if not text:
        return "未确认"
    return re.sub(r"赔率=\d+(?:\.\d+)?", "赔率坐标", text)


def summarize_opening_intervals(intervals: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Return stable interval labels without carrying raw odds decimals into keys."""

    return {
        company: {
            side: _coordinate_summary(values.get(side, "未确认"))
            for side in ("home", "draw", "away")
        }
        for company, values in sorted(intervals.items())
    }


def _water_label(value: str) -> str:
    for water in ("高水", "中水", "低水"):
        if water in value:
            return water.replace("水", "")
    return "未确认"


def _water_shape(intervals: dict[str, dict[str, str]]) -> str:
    labels: list[str] = []
    for side, label in (("home", "主"), ("draw", "平"), ("away", "负")):
        waters = [_water_label(values.get(side, "")) for values in intervals.values()]
        water = Counter(waters).most_common(1)[0][0] if waters else "未确认"
        labels.append(f"{label}{water}")
    return "_".join(labels)


def build_interval_fingerprint(snapshot: PrematchSnapshot) -> dict[str, Any]:
    return {
        "theoretical_system": snapshot.theoretical_system,
        "theoretical_interval": snapshot.theoretical_interval,
        "actual_opening_interval": snapshot.actual_opening_interval,
        "actual_latest_interval": snapshot.actual_latest_interval,
        "opening_interval_relation": _opening_interval_relation(snapshot.opening_deviation),
        "water_shape": _water_shape(snapshot.actual_opening_interval),
    }


def _movement_by_side(snapshot: PrematchSnapshot) -> dict[str, str]:
    moves = snapshot.company_motive_chain.get("movement", {}).get("moves", [])
    actions: dict[str, list[str]] = {"胜": [], "平": [], "负": []}
    if isinstance(moves, list):
        for move in moves:
            if not isinstance(move, dict):
                continue
            side = _side(move.get("direction"))
            action = move.get("action")
            if side in actions and action in MOVE_VALUES:
                actions[side].append(action)
    result: dict[str, str] = {}
    for side, values in actions.items():
        if not values:
            result[side] = "无数据"
            continue
        counts = Counter(values)
        result[side] = counts.most_common(1)[0][0] if len(counts) == 1 else "稳定"
    return result


def _movement_reading_summary(snapshot: PrematchSnapshot, field: str) -> str:
    readings = snapshot.company_motive_chain.get("movement", {}).get("motive_readings", [])
    values: dict[str, list[str]] = {"胜": [], "平": [], "负": []}
    if isinstance(readings, list):
        for reading in readings:
            if not isinstance(reading, dict):
                continue
            side = _side(reading.get("direction"))
            value = reading.get(field)
            if side in values and isinstance(value, str) and value:
                values[side].append(value)
    return "|".join(
        f"{side}:{Counter(items).most_common(1)[0][0] if items else '无数据'}"
        for side, items in values.items()
    )


def _odds_face_summary(value: Any, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    summary = re.split(r"[（(](?:机构原始赔率|转换后)双公司均值变化", value, maxsplit=1)[0].strip()
    return re.sub(r"[+-]?\d+\.\d+", "数值", summary)


def build_movement_fingerprint(snapshot: PrematchSnapshot) -> dict[str, Any]:
    movement = _movement_by_side(snapshot)
    chain = snapshot.company_motive_chain.get("movement", {})
    odds_face = chain.get("odds_face_change") if isinstance(chain, dict) else None
    fallback = f"胜{movement['胜']}_平{movement['平']}_负{movement['负']}"
    return {
        "home_move_type": movement["胜"],
        "draw_move_type": movement["平"],
        "away_move_type": movement["负"],
        "odds_face_change": _odds_face_summary(odds_face, fallback),
        "confidence_bearing_change": _movement_reading_summary(snapshot, "confidence_carrying"),
        "dispersion_effectiveness": _movement_reading_summary(snapshot, "dispersion_effectiveness"),
        "company_alignment": snapshot.company_alignment,
    }


def build_structure_key_coarse(distribution_fingerprint: dict[str, Any]) -> str:
    """Build a coarse key from the original distribution layer only."""

    return "|".join(
        [
            str(distribution_fingerprint.get("original_distribution_type") or ""),
            str(distribution_fingerprint.get("distribution_subtype") or ""),
            str(distribution_fingerprint.get("confidence_bearing_side") or "无"),
            str(distribution_fingerprint.get("natural_heat_side") or "无"),
            ",".join(_ordered_sides(distribution_fingerprint.get("dispersion_sides", []))),
            str(distribution_fingerprint.get("danger_side") or "无"),
        ]
    )


def build_structure_key_exact(
    distribution_fingerprint: dict[str, Any],
    interval_fingerprint: dict[str, Any],
) -> str:
    """Build an exact pre-match structure key without a decision direction."""

    return _stable_key(
        {
            "distribution": {
                "original_distribution_type": distribution_fingerprint.get("original_distribution_type"),
                "distribution_subtype": distribution_fingerprint.get("distribution_subtype"),
                "market_pull_map": distribution_fingerprint.get("market_pull_map"),
                "confidence_bearing_side": distribution_fingerprint.get("confidence_bearing_side"),
                "natural_heat_side": distribution_fingerprint.get("natural_heat_side"),
                "dispersion_sides": _ordered_sides(distribution_fingerprint.get("dispersion_sides", [])),
                "danger_side": distribution_fingerprint.get("danger_side"),
            },
            "interval": {
                "theoretical_system": interval_fingerprint.get("theoretical_system"),
                "theoretical_interval": interval_fingerprint.get("theoretical_interval"),
                "actual_opening_interval": summarize_opening_intervals(
                    interval_fingerprint.get("actual_opening_interval", {})
                ),
                "opening_interval_relation": interval_fingerprint.get("opening_interval_relation"),
                "water_shape": interval_fingerprint.get("water_shape"),
            },
        }
    )


def build_movement_key(movement_fingerprint: dict[str, Any]) -> str:
    """Build an action-only movement key. Raw odds delta decimals are excluded."""

    return _stable_key(
        {
            "home_move_type": movement_fingerprint.get("home_move_type"),
            "draw_move_type": movement_fingerprint.get("draw_move_type"),
            "away_move_type": movement_fingerprint.get("away_move_type"),
            "odds_face_change": movement_fingerprint.get("odds_face_change"),
            "confidence_bearing_change": movement_fingerprint.get("confidence_bearing_change"),
            "dispersion_effectiveness": movement_fingerprint.get("dispersion_effectiveness"),
            "company_alignment": movement_fingerprint.get("company_alignment"),
        }
    )


def build_decision_key(
    *,
    structure_key_exact: str,
    final_direction: str,
    candidate_mainline: str,
) -> str:
    """Build a decision-only comparison key, never a primary matching key."""

    return _stable_key(
        {
            "structure_key_exact": structure_key_exact,
            "final_direction": final_direction,
            "candidate_mainline": candidate_mainline,
        }
    )


def build_fingerprint(snapshot: PrematchSnapshot) -> dict[str, Any]:
    distribution = build_distribution_fingerprint(snapshot)
    interval = build_interval_fingerprint(snapshot)
    movement = build_movement_fingerprint(snapshot)
    coarse_key = build_structure_key_coarse(distribution)
    exact_key = build_structure_key_exact(distribution, interval)
    movement_key = build_movement_key(movement)
    decision_key = build_decision_key(
        structure_key_exact=exact_key,
        final_direction=snapshot.final_direction,
        candidate_mainline=snapshot.relative_mainline_selection,
    )
    return {
        "schema_version": "0.2",
        "fingerprint_version": "0.3",
        "match_id": snapshot.match_id,
        "competition": snapshot.competition,
        "neutral_ground": snapshot.neutral_ground,
        "home_strength_grade": snapshot.home_strength_grade,
        "away_strength_grade": snapshot.away_strength_grade,
        "strength_diff": snapshot.strength_diff,
        "theoretical_interval": snapshot.theoretical_interval,
        "theoretical_system": snapshot.theoretical_system,
        "actual_opening_interval": snapshot.actual_opening_interval,
        "actual_latest_interval": snapshot.actual_latest_interval,
        "opening_deviation": snapshot.opening_deviation,
        "odds_move_deviation": snapshot.odds_move_deviation,
        "odds_pattern_tags": list(snapshot.odds_pattern_tags),
        "company_alignment": snapshot.company_alignment,
        "unfavorable_directions": list(snapshot.unfavorable_directions),
        "unfavorable_score_patterns": list(snapshot.unfavorable_score_patterns),
        "relative_mainline_selection": snapshot.relative_mainline_selection,
        "candidate_mainline": snapshot.relative_mainline_selection,
        "final_direction": snapshot.final_direction,
        "distribution_fingerprint": distribution,
        "interval_fingerprint": interval,
        "movement_fingerprint": movement,
        "structure_key_coarse": coarse_key,
        "structure_key_exact": exact_key,
        "movement_key": movement_key,
        "decision_key": decision_key,
        # Retained for v1.1.1 consumers. New experience matching does not use it.
        "structure_key": exact_key,
        "similar_sample_key": coarse_key,
    }


def _forbidden_paths(value: Any, path: str = "prematch_fingerprint") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            current = f"{path}.{key}"
            if key in FORBIDDEN_CURRENT_RESULT_KEYS:
                found.append(current)
            found.extend(_forbidden_paths(nested, current))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return found


def validate_fingerprint(data: dict[str, Any]) -> dict[str, Any]:
    fingerprint = require_dict(data, "prematch_fingerprint")
    forbidden = _forbidden_paths(fingerprint)
    if forbidden:
        raise SharedValidationError(
            f"prematch_fingerprint must not contain current result fields: {', '.join(sorted(forbidden))}"
        )
    return fingerprint
