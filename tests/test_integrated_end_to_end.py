from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from focas_experience.report import build_experience_report, query_experience
from focas_postmatch.review import review_files
from focas_postmatch.store import add_sample, rebuild_index
from focas_prematch.snapshot import analyze_match_package
from shared.fingerprint import build_fingerprint
from shared.prematch_schema import PrematchSnapshot
from shared.validators import SharedValidationError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _match_package(tmp_path: Path) -> Path:
    package = tmp_path / "match.zip"
    canonical = PROJECT_ROOT / "examples" / "valid_complete_match_input.json"
    with zipfile.ZipFile(package, "w") as archive:
        archive.write(canonical, arcname="match.json")
    return package


def test_end_to_end_modules_are_isolated(tmp_path, monkeypatch, default_corrected_table) -> None:
    monkeypatch.setenv("FOCAS_POSTMATCH_DATA_DIR", str(tmp_path / "data" / "postmatch"))
    rules_file = tmp_path / "P1-P9-rules.txt"
    rules_file.write_text("赛前规则不得被赛后模块改写", encoding="utf-8")

    prematch_path = tmp_path / "prematch_snapshot.json"
    fingerprint_path = tmp_path / "prematch_fingerprint.json"
    snapshot = analyze_match_package(
        _match_package(tmp_path),
        out=prematch_path,
        fingerprint_out=fingerprint_path,
        table_path=default_corrected_table,
    )
    loaded_snapshot = PrematchSnapshot.from_dict(json.loads(prematch_path.read_text(encoding="utf-8")))
    assert loaded_snapshot.match_id == snapshot.match_id
    assert snapshot.final_direction == "PASS"
    assert snapshot.decision_status == "OBSERVE"
    assert snapshot.structural_lean in {"胜", "平", "负"}
    for intervals in snapshot.actual_opening_interval.values():
        assert set(intervals) == {"home", "draw", "away"}
    for intervals in snapshot.actual_latest_interval.values():
        assert set(intervals) == {"home", "draw", "away"}

    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps({"home_goals": 1, "away_goals": 0, "logic_hit": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    sample_path = tmp_path / "postmatch_sample.json"
    sample = review_files(prematch_path, result_path, sample_path)
    assert sample.validation.direction_hit is False
    assert sample.validation.score_range_hit is False
    assert sample.validation.margin_hit is False

    sample_id = add_sample(sample)
    index = rebuild_index()
    assert index["total_samples"] == 1
    assert sample_id in index["samples"]
    assert (tmp_path / "data" / "postmatch" / "postmatch_samples.jsonl").read_text(encoding="utf-8").strip()

    next_fingerprint = build_fingerprint(snapshot)
    fingerprint_path.write_text(json.dumps(next_fingerprint, ensure_ascii=False), encoding="utf-8")
    report_path = tmp_path / "experience_report.json"
    report = query_experience(fingerprint_path, report_path)
    assert report["sample_count"] == 1
    assert report["experience_level"] == "C"
    assert "不得单独决定最终方向" in report["explanation"]
    assert report_path.exists()

    assert rules_file.read_text(encoding="utf-8") == "赛前规则不得被赛后模块改写"


def test_experience_fingerprint_rejects_current_match_result_fields() -> None:
    with pytest.raises(SharedValidationError):
        build_experience_report(
            {
                "similar_sample_key": "测试",
                "result": {"outcome": "胜"},
            }
        )
