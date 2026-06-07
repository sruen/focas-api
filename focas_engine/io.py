from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
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


def _known_fields(cls: type, data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    allowed = {item.name for item in fields(cls)}
    return {key: value for key, value in data.items() if key in allowed}


def _team(data: dict[str, Any] | None) -> TeamContext | None:
    if data is None:
        return None
    return TeamContext(**_known_fields(TeamContext, data))


def _h2h(data: dict[str, Any] | None) -> H2HContext | None:
    if data is None:
        return None
    return H2HContext(**_known_fields(H2HContext, data))


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


def _compact_text(value: Any, *, limit: int = 260) -> str:
    return " ".join(_flatten_text(value).split())[:limit]


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(key in text for key in keywords)


def _single_leg_from_text(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "")
    if _contains_any(text, ("单回合", "单场", "单场比赛", "一场定胜负", "single leg", "single-leg", "one-off")):
        return True
    if _contains_any(text, ("两回合", "双回合", "two legs", "two-legged")):
        return False
    return None


def _normalize_direction(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"home", "h", "主胜", "胜", "主队", "主", "涓昏儨"}:
        return "主胜"
    if text in {"draw", "d", "平局", "平", "骞冲眬"}:
        return "平局"
    if text in {"away", "a", "客胜", "负", "客队", "客", "瀹㈣儨"}:
        return "客胜"
    return str(value or "").strip()


def _normalize_strength(value: Any, score: Any = None) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"强", "strong", "high", "高"}:
        return "强"
    if text in {"中", "medium", "mid"}:
        return "中"
    if text in {"弱", "weak", "low", "低"}:
        return "弱"
    raw_score = str(score or "").strip()
    if raw_score.startswith("+2") or raw_score.startswith("2"):
        return "强"
    if raw_score.startswith("+1") or raw_score.startswith("1") or raw_score == "0":
        return "中"
    if raw_score.startswith("-"):
        return "弱"
    return str(value or "").strip() or None


def _normalize_pull_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    out["direction"] = _normalize_direction(out.get("direction"))
    out["strength"] = _normalize_strength(out.get("strength"), out.get("pull_score"))
    if not out.get("market_psychology"):
        out["market_psychology"] = out.get("market_visibility") or out.get("facts")
    if not out.get("popularity_direction"):
        out["popularity_direction"] = out.get("market_visibility") or out.get("facts")
    if out.get("easy_to_receive") is None:
        visibility = str(out.get("market_visibility") or "")
        out["easy_to_receive"] = _contains_any(visibility, ("高", "中", "high", "medium"))
    if out.get("first_eye_direction") is None:
        out["first_eye_direction"] = str(out.get("pull_score") or "").startswith("+2")
    return out


def _normalize_narrative_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    out["direction"] = _normalize_direction(out.get("direction"))
    return out


def _friendly_defaults(match_data: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(match_data)
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
    data["result_scope"] = _first_present(data, "result_scope", "settlement_scope", "result_rule")

    text = _flatten_text([data, raw.get("home_context"), raw.get("away_context"), raw.get("h2h"), raw.get("narrative_materials")])
    is_friendly = _contains_any(text, ("友谊", "友谊赛", "热身", "friendly", "Friendly"))
    single_rule = _single_leg_from_text(text)
    no_extra_rule = _contains_any(
        text,
        ("90分钟", "常规时间", "无加时", "无加时赛", "没有加时", "无点球", "无点球大战", "no extra time", "no penalties"),
    )

    if is_friendly or single_rule is not None or no_extra_rule:
        if not data.get("stage"):
            data["stage"] = data.get("match_type") or data.get("competition") or "单场90分钟比赛"
        if _single_leg_from_text(data.get("single_leg")) is not None:
            data["single_leg"] = _single_leg_from_text(data.get("single_leg"))
        elif data.get("single_leg") in (None, ""):
            data["single_leg"] = True
        if not data.get("extra_time_or_penalties"):
            data["extra_time_or_penalties"] = "无加时或点球规则，按90分钟常规时间审计"
        if not data.get("result_scope"):
            data["result_scope"] = "90分钟常规时间"
        if not data.get("attention_level"):
            data["attention_level"] = (
                "国家队友谊赛/热身赛，受注关注度按中等以上处理，需GPT结合球队名气复核"
                if is_friendly
                else "赛事关注度由赛前材料自动归一化，需GPT复核"
            )
    return data


def _team_defaults(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    out = dict(data)
    if not out.get("rank"):
        out["rank"] = _first_present(out, "ranking", "fifa_rank", "rank_context", "ranking_context")
    if not out.get("points"):
        out["points"] = _first_present(out, "league_points", "points_context", "ranking_points", "table_points")
    if not out.get("injuries"):
        out["injuries"] = _first_present(out, "injury_news", "unavailable_players", "team_news", "suspensions")
    if not out.get("injuries") or (
        isinstance(out.get("injuries"), str)
        and any(marker in out["injuries"] for marker in ("待确认", "暂无", "未知", "未确认"))
    ):
        out["injuries"] = "赛前公开资料存在伤疑或名单完整度变量，按低可信阵容信息记录，需GPT复核来源后降级使用。"
    recent = out.get("recent_matches") or []
    recent_text = "；".join(str(item) for item in recent[:3]) if isinstance(recent, list) else str(recent)
    summary = _compact_text([out.get("recent_record_summary"), out.get("recent_goals_for_against"), recent_text])

    if not out.get("attack_state"):
        out["attack_state"] = _compact_text([out.get("recent_goals_for_against"), out.get("tactical_style"), summary]) or "进攻状态需GPT复核"
    if not out.get("defense_state"):
        out["defense_state"] = _compact_text([out.get("recent_goals_for_against"), out.get("tactical_style"), summary]) or "防守状态需GPT复核"
    if not out.get("major_recent_matches"):
        out["major_recent_matches"] = _first_present(
            out,
            "major_recent_match",
            "major_recent_match_signal",
            "key_recent_match",
            "key_recent_matches",
        )
    if not out.get("major_recent_matches"):
        out["major_recent_matches"] = (
            f"由近5-6场自动归纳近期重大比赛表现：{recent_text}。具体含金量由GPT赛前审计。"
            if recent_text
            else "未发现单独重大近赛样本；按无强重大近赛题材处理，需GPT复核。"
        )
    return out


def _h2h_defaults(data: dict[str, Any] | None, raw: dict[str, Any]) -> dict[str, Any] | None:
    if data is None:
        return None
    out = dict(data)
    if not out.get("latest_key_match"):
        out["latest_key_match"] = _first_present(out, "latest_key_h2h", "key_match", "recent_key_match")
    if not out.get("latest_key_match"):
        source = _compact_text([out.get("recent_years"), out.get("overall"), out.get("market_psychology"), raw.get("narrative_materials")])
        out["latest_key_match"] = (
            f"由往绩材料自动归纳最近关键交锋：{source}。具体关键性由GPT复核。"
            if source
            else "未发现明确最近关键交锋；按往绩题材弱处理，需GPT复核。"
        )
    if not out.get("same_competition"):
        out["same_competition"] = "同赛事交锋样本未明确；按往绩辅助项处理。"
    if not out.get("venue_specific"):
        out["venue_specific"] = "主客/中立场交锋样本未明确；按往绩辅助项处理。"
    if not out.get("market_psychology"):
        out["market_psychology"] = _compact_text([out.get("overall"), out.get("recent_years"), out.get("latest_key_match")]) or "往绩市场心理由GPT复核"
    return out


def parse_raw_input(
    raw: dict[str, Any],
    *,
    diagnostics: list[PackageDiagnostic] | None = None,
    source_files: list[str] | None = None,
) -> LoadedInput:
    match_data = _friendly_defaults(raw["match"], raw)
    home_data = _team_defaults(raw.get("home_context"))
    away_data = _team_defaults(raw.get("away_context"))
    h2h_data = _h2h_defaults(raw.get("h2h"), raw)
    if home_data is not None and not home_data.get("name"):
        home_data["name"] = match_data.get("home_team", "未识别主队")
    if away_data is not None and not away_data.get("name"):
        away_data["name"] = match_data.get("away_team", "未识别客队")

    match = MatchContext(
        home_team=match_data.get("home_team", "未识别主队"),
        away_team=match_data.get("away_team", "未识别客队"),
        competition=match_data.get("competition"),
        kickoff_time=match_data.get("kickoff_time"),
        stage=match_data.get("stage"),
        neutral_venue=match_data.get("neutral_venue"),
        single_leg=match_data.get("single_leg"),
        match_type=match_data.get("match_type"),
        extra_time_or_penalties=match_data.get("extra_time_or_penalties"),
        result_scope=match_data.get("result_scope"),
        real_home_away=match_data.get("real_home_away"),
        attention_level=match_data.get("attention_level"),
        league_for_table=match_data.get("league_for_table"),
        home=_team(home_data),
        away=_team(away_data),
        h2h=_h2h(h2h_data),
    )
    strength = StrengthContext(**_known_fields(StrengthContext, raw.get("strength", {})))
    pulls = [
        NaturalPull(**_known_fields(NaturalPull, _normalize_pull_payload(p)))
        for p in raw.get("natural_pulls", [])
    ]
    narrative_materials = [
        NarrativeMaterial(**_known_fields(NarrativeMaterial, _normalize_narrative_payload(p)))
        for p in raw.get("narrative_materials", [])
    ]
    book_mode = OriginalBookMode(**_known_fields(OriginalBookMode, raw.get("original_book_mode", {})))
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
