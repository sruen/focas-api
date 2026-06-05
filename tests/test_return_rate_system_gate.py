from __future__ import annotations

import re
from pathlib import Path

import pytest

from focas_engine.config import HARD_DATA_SOURCE, LEGACY_HARD_DATA_SOURCES
from focas_engine.io import load_input
from focas_engine.models import OddsSnapshot, StrengthContext
from focas_engine.odds_system import build_odds_system_conversions, convert_snapshot_to_system
from focas_engine.pipeline import FocasPipeline
from focas_engine.report import render_frontend_report


def _load():
    return load_input(Path(__file__).parents[1] / "examples" / "valid_complete_match_input.json")


def _run(table_path: str | None):
    match, strength, pulls, mode, odds = _load()
    return FocasPipeline(table_path=table_path).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )


def test_default_hard_data_source_reads_corrected_market_ladder(default_corrected_table, monkeypatch):
    monkeypatch.chdir(Path(default_corrected_table).parent)
    result = _run(None)
    assert result.stop is False
    assert result.hard_data_source == HARD_DATA_SOURCE
    assert all(item.sheet_name.endswith("体系") for item in result.table_results)


def test_legacy_table_never_unlocks_default_pipeline(tmp_path, monkeypatch):
    legacy = next(iter(LEGACY_HARD_DATA_SOURCES))
    (tmp_path / legacy).write_bytes(b"legacy")
    monkeypatch.chdir(tmp_path)
    result = _run(None)
    assert result.stop is True
    assert result.table_read_confirmed == "NO"
    assert result.mainline_output_status == "FORBIDDEN"


def test_explicit_legacy_table_is_rejected(tmp_path):
    legacy = tmp_path / next(iter(LEGACY_HARD_DATA_SOURCES))
    legacy.write_bytes(b"legacy")
    result = _run(str(legacy))
    assert result.stop is True
    assert result.stop_node == "现代骨架数据源闸门"


@pytest.mark.parametrize(
    ("competition", "match_type", "neutral"),
    [
        ("芬超", "联赛", False),
        ("瑞超", "联赛", False),
        ("国家杯", "杯赛淘汰赛", False),
        ("国际国家队邀请赛", "国家队赛事小组赛", True),
    ],
)
def test_event_context_does_not_gate_system_lookup(mini_table, competition, match_type, neutral):
    match, strength, pulls, mode, odds = _load()
    match.competition = competition
    match.league_for_table = competition
    match.match_type = match_type
    match.stage = "小组赛第2轮" if "小组" in match_type else "联赛第12轮"
    match.neutral_venue = neutral
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is False
    assert result.table_read_confirmed == "YES"
    assert competition in result.context_modifiers.league_context_modifier


def test_missing_league_for_table_does_not_block_lookup(mini_table):
    match, strength, pulls, mode, odds = _load()
    match.league_for_table = None
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is False
    assert result.table_read_confirmed == "YES"


def test_each_snapshot_uses_its_actual_return_rate_system():
    initial = convert_snapshot_to_system(company="William", snapshot_type="initial", snapshot=OddsSnapshot(2.10, 3.20, 3.60))
    current = convert_snapshot_to_system(company="William", snapshot_type="current", snapshot=OddsSnapshot(2.20, 3.20, 3.60))
    assert initial.detected_system != current.detected_system
    assert initial.system_lookup_status == "SYSTEM_LOOKUP_ALLOWED"
    assert current.system_lookup_status == "SYSTEM_LOOKUP_ALLOWED"


def test_unrecognized_return_rate_forbids_mainline(mini_table):
    match, strength, pulls, mode, odds = _load()
    odds[0].initial = OddsSnapshot(3.0, 4.0, 5.0)
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is True
    assert result.table_read_confirmed == "NO"
    assert result.mainline_output_status == "FORBIDDEN"
    assert result.report_mode == "STOP_REPORT_ONLY"


def test_table_gate_stop_example_refuses_unrecognized_system(mini_table):
    source_root = Path(__file__).parents[1]
    match, strength, pulls, mode, odds = load_input(source_root / "examples" / "table_gate_stop_case.json")
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is True
    assert result.table_read_confirmed == "NO"
    assert result.mainline_output_status == "FORBIDDEN"
    assert result.report_mode == "STOP_REPORT_ONLY"


def test_p4_review_does_not_erase_real_xlsx_lookup(mini_table):
    match, _, pulls, mode, odds = _load()
    strength = StrengthContext(
        home_grade="人强",
        away_grade="下游",
        static_gap="主队高4.5档",
        dynamic_adjustment="人工校准后维持",
        final_gap="主队高4.5档",
    )
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    assert result.stop is False
    assert result.expected_interval_status == "REVIEW_REQUIRED"
    assert result.table_read_confirmed == "YES"


def test_frontend_lookup_evidence_and_float_format(mini_table):
    match, strength, pulls, mode, odds = _load()
    result = FocasPipeline(table_path=mini_table).run(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds
    )
    text = render_frontend_report(
        match=match, strength=strength, pulls=pulls, book_mode=mode, odds=odds, result=result
    )
    for field in ("公司", "时点", "赔率", "返还率", "识别体系", "最低项", "低赔轴区间", "水位", "边界距离", "lookup_status"):
        assert field in text
    assert HARD_DATA_SOURCE in text
    assert re.search(r"\d+\.\d{7,}", text) is None


def test_no_single_mainline_token_removed():
    project_root = Path(__file__).parents[1]
    files = [path for path in project_root.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in files if path.suffix in {".py", ".md", ".toml", ".json"})
    forbidden = "NO_" + "SINGLE_MAINLINE"
    assert forbidden not in text
