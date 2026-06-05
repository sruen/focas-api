from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import (
    CompanyOdds,
    H2HContext,
    MatchContext,
    NarrativeMaterial,
    NaturalPull,
    OddsSnapshot,
    OriginalBookMode,
    StrengthContext,
    TeamContext,
)
from .match_package_loader import PackageDiagnostic, load_package


@dataclass
class LoadedInput:
    match: MatchContext
    strength: StrengthContext
    pulls: list[NaturalPull]
    book_mode: OriginalBookMode
    odds: list[CompanyOdds]
    raw: dict[str, Any]
    narrative_materials: list[NarrativeMaterial] = field(default_factory=list)
    diagnostics: list[PackageDiagnostic] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def as_tuple(self):
        return self.match, self.strength, self.pulls, self.book_mode, self.odds


def _team(data: dict[str, Any] | None) -> TeamContext | None:
    if data is None:
        return None
    return TeamContext(**data)


def _h2h(data: dict[str, Any] | None) -> H2HContext | None:
    if data is None:
        return None
    return H2HContext(**data)


def _snapshot(data: dict[str, Any]) -> OddsSnapshot:
    return OddsSnapshot(home=float(data["home"]), draw=float(data["draw"]), away=float(data["away"]))


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _bool_from_text(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "")
    if any(key in text for key in ("单回合", "单场", "single leg", "single-leg", "one-off", "一场定胜负")):
        return True
    if any(key in text for key in ("两回合", "双回合", "two legs", "two-legged")):
        return False
    return None


def _friendly_defaults(m: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """Fill stable match-rule fields for friendlies.

    GPT Actions may place "友谊赛、单回合、无加时点球" into competition or
    match_type, team motivation, or other text fields. The engine gate needs the
    normalized fields separately.
    """
    data = dict(m)
    data["stage"] = _first_present(data, "stage", "match_stage", "phase", "round", "match_phase")
    data["single_leg"] = _first_present(
        data,
        "single_leg",
        "single_match",
        "single_game",
        "single_round",
        "is_single_leg",
        "one_off",
    )
    data["extra_time_or_penalties"] = _first_present(
        data,
        "extra_time_or_penalties",
        "extra_time_rule",
        "penalty_rule",
        "match_rules",
        "result_scope",
        "settlement_scope",
    )

    text = " ".join(
        [
            str(data.get(key) or "")
            for key in ("competition", "match_type", "stage", "extra_time_or_penalties")
        ]
    )
    text = f"{text} {_flatten_text(raw.get('home_context'))} {_flatten_text(raw.get('away_context'))} {_flatten_text(raw.get('h2h'))} {_flatten_text(raw.get('narrative_materials'))}"
    is_friendly = any(key in text for key in ("友谊", "friendly", "Friendly", "热身"))
    has_single_rule = _bool_from_text(text)
    has_no_extra_rule = any(
        key in text
        for key in (
            "90分钟",
            "常规时间",
            "无加时",
            "无加时赛",
            "没有加时",
            "无点球",
            "无点球大战",
            "no extra time",
            "no penalties",
        )
    )
    if is_friendly or has_single_rule is not None or has_no_extra_rule:
        if not data.get("stage"):
            data["stage"] = data.get("match_type") or data.get("competition") or "常规90分钟单场比赛"
        if _bool_from_text(data.get("single_leg")) is not None:
            data["single_leg"] = _bool_from_text(data.get("single_leg"))
        elif data.get("single_leg") is None or data.get("single_leg") == "":
            data["single_leg"] = True if (is_friendly or has_single_rule) else None
        if not data.get("extra_time_or_penalties"):
            data["extra_time_or_penalties"] = (
                "无加时或点球规则，按90分钟常规时间审计"
                if has_no_extra_rule or is_friendly
                else "加时/点球规则未明确，按用户文本规则审计"
            )
    return data


def parse_raw_input(raw: dict[str, Any], *, diagnostics: list[PackageDiagnostic] | None = None, source_files: list[str] | None = None) -> LoadedInput:
    m = _friendly_defaults(raw["match"], raw)
    match = MatchContext(
        home_team=m.get("home_team", "未识别主队"),
        away_team=m.get("away_team", "未识别客队"),
        competition=m.get("competition"),
        kickoff_time=m.get("kickoff_time"),
        stage=m.get("stage"),
        neutral_venue=m.get("neutral_venue"),
        single_leg=m.get("single_leg"),
        match_type=m.get("match_type"),
        extra_time_or_penalties=m.get("extra_time_or_penalties"),
        real_home_away=m.get("real_home_away"),
        attention_level=m.get("attention_level"),
        league_for_table=m.get("league_for_table"),
        home=_team(raw.get("home_context")),
        away=_team(raw.get("away_context")),
        h2h=_h2h(raw.get("h2h")),
    )
    strength = StrengthContext(**raw.get("strength", {}))
    pulls = [NaturalPull(**p) for p in raw.get("natural_pulls", [])]
    narrative_materials = [NarrativeMaterial(**p) for p in raw.get("narrative_materials", [])]
    book_mode = OriginalBookMode(**raw.get("original_book_mode", {}))
    odds = [
        CompanyOdds(
            company=o["company"],
            initial=_snapshot(o["initial"]),
            current=_snapshot(o["current"]),
        )
        for o in raw.get("odds", [])
    ]
    return LoadedInput(
        match=match,
        strength=strength,
        pulls=pulls,
        book_mode=book_mode,
        odds=odds,
        raw=raw,
        narrative_materials=narrative_materials,
        diagnostics=diagnostics or [],
        source_files=source_files or [],
    )


def load_input_with_report(path: str | Path) -> LoadedInput:
    p = Path(path)
    if p.suffix.lower() == ".zip":
        pkg = load_package(p)
        return parse_raw_input(pkg.raw, diagnostics=pkg.diagnostics, source_files=pkg.source_files)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return parse_raw_input(raw)


def load_input(path: str | Path):
    """Backward-compatible loader returning the old 5-tuple."""
    return load_input_with_report(path).as_tuple()
