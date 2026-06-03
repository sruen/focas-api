from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from focas_experience.report import build_experience_report
from focas_postmatch.cli import main as postmatch_main
from focas_postmatch.review import review_files
from focas_postmatch.store import add_sample
from focas_prematch.cli import main as prematch_main
from focas_prematch.snapshot import analyze_match_package
from shared.fingerprint import build_fingerprint, validate_fingerprint
from shared.validators import SharedValidationError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _match_package(tmp_path: Path, name: str = "match.zip") -> Path:
    package = tmp_path / name
    canonical = PROJECT_ROOT / "examples" / "valid_complete_match_input.json"
    with zipfile.ZipFile(package, "w") as archive:
        archive.write(canonical, arcname="match.json")
    return package


def _snapshot(tmp_path: Path, table: str):
    return analyze_match_package(_match_package(tmp_path), table_path=table)


def _review_sample(tmp_path: Path, snapshot_path: Path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"home_goals": 1, "away_goals": 0, "logic_hit": True}), encoding="utf-8")
    sample_path = tmp_path / "postmatch_sample.json"
    sample = review_files(snapshot_path, result_path, sample_path)
    return sample, sample_path


def test_structure_key_excludes_direction_but_decision_key_contains_it(tmp_path, default_corrected_table) -> None:
    fingerprint = build_fingerprint(_snapshot(tmp_path, default_corrected_table))
    structure = json.loads(fingerprint["structure_key_exact"])
    decision = json.loads(fingerprint["decision_key"])
    assert "final_direction" not in structure
    assert "relative_mainline_selection" not in structure
    assert decision["candidate_mainline"] == "胜"
    assert decision["final_direction"] == "胜"


@pytest.mark.parametrize("field", ["result", "final_score", "outcome"])
def test_fingerprint_rejects_current_match_result_fields(field) -> None:
    with pytest.raises(SharedValidationError):
        validate_fingerprint({field: "当前比赛赛果不得进入 fingerprint"})


def test_experience_prefers_structure_key_and_returns_outcome_distribution(
    tmp_path, monkeypatch, default_corrected_table
) -> None:
    monkeypatch.setenv("FOCAS_POSTMATCH_DATA_DIR", str(tmp_path / "data" / "postmatch"))
    snapshot_path = tmp_path / "prematch_snapshot.json"
    snapshot = analyze_match_package(_match_package(tmp_path), out=snapshot_path, table_path=default_corrected_table)
    sample, _ = _review_sample(tmp_path, snapshot_path)
    sample.promotion.similar_sample_key = "legacy-key-that-does-not-match"
    add_sample(sample)

    report = build_experience_report(build_fingerprint(snapshot))
    assert report["matched_by"] == "movement_key"
    assert report["structure_sample_count"] == 1
    assert report["decision_sample_count"] == 1
    assert report["outcome_distribution"] == {"胜": 1}
    assert report["prematch_direction_distribution"] == {"胜": 1}


def test_prematch_with_experience_writes_report_without_changing_direction(
    tmp_path, monkeypatch, default_corrected_table, capsys
) -> None:
    monkeypatch.setenv("FOCAS_POSTMATCH_DATA_DIR", str(tmp_path / "data" / "postmatch"))
    package = _match_package(tmp_path)
    snapshot_path = tmp_path / "prematch_snapshot.json"
    fingerprint_path = tmp_path / "prematch_fingerprint.json"
    experience_path = tmp_path / "experience_report.json"
    assert (
        prematch_main(
            [
                "analyze",
                "--match-package",
                str(package),
                "--out",
                str(snapshot_path),
                "--fingerprint-out",
                str(fingerprint_path),
                "--experience-out",
                str(experience_path),
                "--with-experience",
                "--table",
                str(default_corrected_table),
            ]
        )
        == 0
    )
    response = json.loads(capsys.readouterr().out)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert experience_path.exists()
    assert snapshot["final_direction"] == "胜"
    assert response["experience_level"] == "D"
    assert response["usable_for_mainline"] is False


def test_postmatch_validate_accepts_valid_and_rejects_invalid_sample(
    tmp_path, monkeypatch, default_corrected_table, capsys
) -> None:
    monkeypatch.setenv("FOCAS_POSTMATCH_DATA_DIR", str(tmp_path / "data" / "postmatch"))
    snapshot_path = tmp_path / "prematch_snapshot.json"
    analyze_match_package(_match_package(tmp_path), out=snapshot_path, table_path=default_corrected_table)
    _, sample_path = _review_sample(tmp_path, snapshot_path)
    assert postmatch_main(["validate", "--file", str(sample_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"valid": True}

    invalid = json.loads(sample_path.read_text(encoding="utf-8"))
    invalid["validation"]["direction_hit"] = False
    invalid_path = tmp_path / "invalid_postmatch_sample.json"
    invalid_path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
    assert postmatch_main(["validate", "--file", str(invalid_path)]) != 0
    assert json.loads(capsys.readouterr().out)["valid"] is False
