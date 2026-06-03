from __future__ import annotations

from focas_engine.models import DirectionJudgement, MatchContext, PipelineResult, RelativeSelectionResult
from focas_engine.oos import (
    build_oos_record,
    direction_from_score,
    normalize_direction,
    append_oos_record,
    load_oos_ledger,
    summarize_oos,
)


def test_direction_helpers():
    assert direction_from_score(2, 1) == "主胜"
    assert direction_from_score(1, 1) == "平局"
    assert direction_from_score(0, 2) == "客胜"
    assert normalize_direction("H") == "主胜"
    assert normalize_direction("D") == "平局"
    assert normalize_direction("A") == "客胜"


def test_oos_hit_record_from_score():
    match = MatchContext("主队", "客队", competition="测试赛", kickoff_time="2026-05-30")
    result = PipelineResult(gates=[])
    result.final_direction = "主胜"

    record = build_oos_record(match=match, result=result, score="2-1")

    assert record.status == "HIT"
    assert record.hit is True
    assert record.predicted_direction == "主胜"
    assert record.actual_direction == "主胜"


def test_oos_miss_actual_was_adverse_exclusion():
    match = MatchContext("主队", "客队")
    result = PipelineResult(gates=[])
    result.final_direction = "客胜"
    result.direction_judgements = [
        DirectionJudgement("主胜", "不利", ["不利证据"]),
        DirectionJudgement("平局", "中性", []),
        DirectionJudgement("客胜", "中性", []),
    ]
    result.relative_selection = RelativeSelectionResult(
        selected_direction="客胜",
        confidence="中",
        method="relative",
        adverse_exclusions=["主胜"],
        relative_non_selected=["平局"],
    )

    record = build_oos_record(match=match, result=result, actual_direction="主胜")

    assert record.status == "MISS"
    assert record.hit is False
    assert record.failure_bucket == "ADVERSE_EXCLUSION_ERROR"
    assert "主胜" in record.adverse_exclusions


def test_oos_ledger_roundtrip_and_summary(tmp_path):
    ledger = tmp_path / "oos.jsonl"
    match = MatchContext("主队", "客队")
    r1 = PipelineResult(gates=[])
    r1.final_direction = "主胜"
    r2 = PipelineResult(gates=[])
    r2.final_direction = "客胜"

    append_oos_record(build_oos_record(match=match, result=r1, actual_direction="主胜"), ledger)
    append_oos_record(build_oos_record(match=match, result=r2, actual_direction="主胜"), ledger)

    rows = load_oos_ledger(ledger)
    summary = summarize_oos(rows)

    assert len(rows) == 2
    assert summary.evaluated == 2
    assert summary.hits == 1
    assert summary.misses == 1
    assert summary.hit_rate == 0.5


def test_oos_record_contains_audit_hashes(tmp_path):
    input_file = tmp_path / "input.json"
    table_file = tmp_path / "table.xlsx"
    input_file.write_text("{}", encoding="utf-8")
    table_file.write_bytes(b"table")
    match = MatchContext("主队", "客队", competition="测试赛", kickoff_time="2026-05-30")
    result = PipelineResult(gates=[])
    result.final_direction = "主胜"

    record = build_oos_record(match=match, result=result, actual_direction="主胜", input_path=input_file, table_path=table_file)

    assert record.engine_version == "1.0.2"
    assert record.created_at
    assert record.match_id
    assert len(record.input_hash) == 64
    assert len(record.table_hash) == 64
