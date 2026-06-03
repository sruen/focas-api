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


def parse_raw_input(raw: dict[str, Any], *, diagnostics: list[PackageDiagnostic] | None = None, source_files: list[str] | None = None) -> LoadedInput:
    m = raw["match"]
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
