from __future__ import annotations

import json
import zipfile
from pathlib import Path

from focas_engine.match_package_loader import load_package
from focas_engine.models import MatchContext, NaturalPull, StrengthContext
from focas_engine.context_modifiers import build_event_context_modifiers
from focas_engine.original_modes import estimate_original_mode


def test_context_payload_enriches_collector_package(tmp_path: Path):
    payload = {
        "match": {
            "home_team": "Home",
            "away_team": "Away",
            "competition": "International Friendly",
            "kickoff_beijing_time": "2026-06-02 00:00",
            "neutral_field": False,
            "single_match": True,
            "extra_time_penalties": False,
            "home_away_attribute_real": True,
        },
        "home_context": {
            "ranking_points_context": "FIFA ranking 88",
            "recent_5": ["W", "W", "W", "L", "L"],
            "home_or_neutral_adaptation": "real home",
            "attack_state": "attack",
            "defense_state": "defense",
            "injuries_squad": "squad",
            "schedule_fitness": "schedule",
            "motivation": "motivation",
            "popularity_story": "story",
            "major_recent_match_signal": "signal",
        },
        "away_context": {
            "ranking_points_context": "FIFA ranking 82",
            "recent_5": ["L", "W", "L", "W", "W"],
            "away_or_neutral_adaptation": "real away",
            "attack_state": "attack",
            "defense_state": "defense",
            "injuries_squad": "squad",
            "schedule_fitness": "schedule",
            "motivation": "motivation",
            "popularity_story": "story",
            "major_recent_match_signal": "signal",
        },
        "h2h_context": {
            "overall_h2h": "eight meetings",
            "recent_h2h": ["latest"],
            "same_competition_h2h": "same competition",
            "home_away_h2h": "venue specific",
            "latest_key_h2h": "latest key match",
            "market_psychology": "market psychology",
        },
        "broad_strength": {
            "home_grade": "\u4e2d\u4e0b",
            "away_grade": "\u4e2d\u6e38",
            "static_grade_gap": "\u5ba2\u961fAway\u9ad8\u7ea60.5\u6863",
            "dynamic_corrections": ["home venue", "away rank"],
            "final_dynamic_strength": "Away remains slightly higher",
        },
        "natural_pull": {
            "home_win_pull": {
                "level": "\u4e2d",
                "basis": "home facts",
                "market_psychology": "home psychology",
                "easy_to_take_bets": True,
                "first_eye_direction": True,
            },
            "draw_pull": {
                "level": "\u4e2d\u504f\u5f3a",
                "basis": "draw facts",
                "market_psychology": "draw psychology",
                "easy_to_take_bets": True,
                "first_eye_direction": False,
            },
            "away_win_pull": {
                "level": "\u4e2d",
                "basis": "away facts",
                "market_psychology": "away psychology",
                "easy_to_take_bets": True,
                "first_eye_direction": False,
            },
        },
    }
    pkg = tmp_path / "context-filled.zip"
    with zipfile.ZipFile(pkg, "w") as zf:
        zf.writestr("123/match_context_payload.json", json.dumps(payload))

    result = load_package(pkg)

    assert result.raw["match"]["home_team"] == "Home"
    assert result.raw["match"]["away_team"] == "Away"
    assert result.raw["match"]["neutral_venue"] is False
    assert result.raw["home_context"]["recent_matches"] == ["W", "W", "W", "L", "L"]
    assert result.raw["h2h"]["overall"] == "eight meetings"
    assert result.raw["strength"]["home_grade"] == "\u4e2d\u4e0b"
    assert result.raw["strength"]["final_gap"].startswith("\u5ba2\u961f\u9ad80.5\u6863")
    assert result.raw["natural_pulls"][1]["strength"] == "\u5f3a"
    assert any("match_context_payload.json" in item.message for item in result.diagnostics)


def test_single_match_friendly_is_not_cup_or_knockout_mode():
    match = MatchContext(
        home_team="Home",
        away_team="Away",
        competition="\u56fd\u9645\u53cb\u8c0a\u8d5b",
        stage="\u56fd\u9645\u53cb\u8c0a\u8d5b",
        match_type="\u56fd\u9645\u53cb\u8c0a\u8d5b",
        single_leg=True,
    )
    strength = StrengthContext(home_grade="\u4e2d\u4e0b", away_grade="\u4e2d\u6e38")
    pulls = [
        NaturalPull("\u4e3b\u80dc", "\u4e2d", "facts", "psychology", "popularity", True, True),
        NaturalPull("\u5e73\u5c40", "\u5f3a", "facts", "psychology", "popularity", True, False),
        NaturalPull("\u5ba2\u80dc", "\u4e2d", "facts", "psychology", "popularity", True, False),
    ]

    estimate = estimate_original_mode(match=match, strength=strength, pulls=pulls)

    assert all(option.mode != "\u676f\u8d5b / \u6dd8\u6c70\u8d5b\u538b\u7f29\u76d8" for option in estimate.options)


def test_friendly_without_extra_time_or_penalties_keeps_negative_rule_tags():
    match = MatchContext(
        home_team="Home",
        away_team="Away",
        competition="\u56fd\u9645\u53cb\u8c0a\u8d5b",
        stage="\u56fd\u9645\u53cb\u8c0a\u8d5b",
        match_type="\u56fd\u9645\u53cb\u8c0a\u8d5b",
        extra_time_or_penalties="\u53cb\u8c0a\u8d5b\u65e0\u52a0\u65f6\u6216\u70b9\u7403\u89c4\u5219",
        single_leg=True,
    )

    modifiers = build_event_context_modifiers(match)

    assert "\u65e0\u52a0\u65f6" in modifiers.detected_event_tags
    assert "\u65e0\u70b9\u7403" in modifiers.detected_event_tags
    assert "\u6709\u52a0\u65f6" not in modifiers.detected_event_tags
    assert "\u6709\u70b9\u7403" not in modifiers.detected_event_tags
