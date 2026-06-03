"""Shared odds and interval coordinate types."""

from __future__ import annotations

from typing import Any, TypeAlias

from .validators import SharedValidationError, require_dict, require_keys, require_str

OddsTriple: TypeAlias = list[int | float]
OddsCoordinates: TypeAlias = dict[str, OddsTriple]
IntervalCoordinate: TypeAlias = dict[str, str]
IntervalCoordinates: TypeAlias = dict[str, IntervalCoordinate]


def validate_odds_coordinates(value: Any, path: str) -> OddsCoordinates:
    companies = require_dict(value, path)
    coordinates: OddsCoordinates = {}
    for company, odds in companies.items():
        require_str(company, f"{path} company", allow_empty=False)
        if not isinstance(odds, list) or len(odds) != 3:
            raise SharedValidationError(f"{path}.{company} must contain exactly [胜, 平, 负] odds")
        checked: OddsTriple = []
        for index, odd in enumerate(odds):
            if not isinstance(odd, (int, float)) or isinstance(odd, bool):
                raise SharedValidationError(f"{path}.{company}[{index}] must be an int or float")
            if odd <= 1.0:
                raise SharedValidationError(f"{path}.{company}[{index}] must be > 1.0")
            checked.append(odd)
        coordinates[company] = checked
    return coordinates


def validate_interval_coordinates(value: Any, path: str) -> IntervalCoordinates:
    companies = require_dict(value, path)
    coordinates: IntervalCoordinates = {}
    for company, intervals in companies.items():
        require_str(company, f"{path} company", allow_empty=False)
        company_intervals = require_dict(intervals, f"{path}.{company}")
        require_keys(company_intervals, ("home", "draw", "away"), f"{path}.{company}")
        coordinates[company] = {
            direction: require_str(company_intervals[direction], f"{path}.{company}.{direction}", allow_empty=False)
            for direction in ("home", "draw", "away")
        }
    return coordinates
