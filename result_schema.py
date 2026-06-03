"""Schema for factual post-match result input."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .validators import SharedValidationError, optional_str, require_bool, require_dict, require_int


@dataclass
class ResultPayload:
    home_goals: int
    away_goals: int
    key_events: list[dict[str, Any]]
    red_cards: list[dict[str, Any]]
    stats: dict[str, Any] | None
    logic_hit: bool | None
    process_risk_covered: bool | None
    validation_summary: str | None
    review: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResultPayload":
        data = require_dict(data, "result")
        home_goals = require_int(data.get("home_goals"), "result.home_goals")
        away_goals = require_int(data.get("away_goals"), "result.away_goals")
        if home_goals < 0 or away_goals < 0:
            raise SharedValidationError("result goals must be >= 0")
        expected = {
            "final_score": f"{home_goals}-{away_goals}",
            "goal_margin": home_goals - away_goals,
        }
        expected["outcome"] = "胜" if expected["goal_margin"] > 0 else "负" if expected["goal_margin"] < 0 else "平"
        for key, value in expected.items():
            if key in data and data[key] != value:
                raise SharedValidationError(f"result.{key} must equal {value}")
        logic_hit = data.get("logic_hit")
        if logic_hit is not None:
            logic_hit = require_bool(logic_hit, "result.logic_hit")
        risk = data.get("process_risk_covered")
        if risk is not None:
            risk = require_bool(risk, "result.process_risk_covered")
        key_events = data.get("key_events", [])
        red_cards = data.get("red_cards", [])
        if not isinstance(key_events, list) or not all(isinstance(item, dict) for item in key_events):
            raise SharedValidationError("result.key_events must be a list of dicts")
        if not isinstance(red_cards, list) or not all(isinstance(item, dict) for item in red_cards):
            raise SharedValidationError("result.red_cards must be a list of dicts")
        stats = data.get("stats")
        if stats is not None:
            stats = require_dict(stats, "result.stats")
        review = data.get("review", {})
        return cls(
            home_goals=home_goals,
            away_goals=away_goals,
            key_events=deepcopy(key_events),
            red_cards=deepcopy(red_cards),
            stats=None if stats is None else deepcopy(stats),
            logic_hit=logic_hit,
            process_risk_covered=risk,
            validation_summary=optional_str(data.get("validation_summary"), "result.validation_summary"),
            review=deepcopy(require_dict(review, "result.review")),
        )

    def factual_result(self) -> dict[str, Any]:
        goal_margin = self.home_goals - self.away_goals
        return {
            "final_score": f"{self.home_goals}-{self.away_goals}",
            "outcome": "胜" if goal_margin > 0 else "负" if goal_margin < 0 else "平",
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
            "goal_margin": goal_margin,
            "key_events": deepcopy(self.key_events),
            "red_cards": deepcopy(self.red_cards),
            "stats": deepcopy(self.stats),
        }
