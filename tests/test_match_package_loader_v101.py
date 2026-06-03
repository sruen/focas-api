from pathlib import Path
import zipfile

from focas_engine.match_package_loader import extract_odds, load_package


def test_extract_odds_labels_two_triples_same_line():
    text = "威廉希尔 初赔 2.10 3.20 3.50 最新 2.20 3.10 3.40\n立博 2.00/3.25/3.60 2.15/3.15/3.30"
    odds = {o["company"]: o for o in extract_odds(text)}
    assert odds["William"]["initial"] == {"home": 2.10, "draw": 3.20, "away": 3.50}
    assert odds["William"]["current"] == {"home": 2.20, "draw": 3.10, "away": 3.40}
    assert odds["Ladbrokes"]["initial"] == {"home": 2.00, "draw": 3.25, "away": 3.60}
    assert odds["Ladbrokes"]["current"] == {"home": 2.15, "draw": 3.15, "away": 3.30}


def test_odds_package_diagnostic(tmp_path: Path):
    pkg = tmp_path / "odds_pkg.zip"
    md = """
比赛：墨西哥 VS 澳大利亚
赛事：友谊赛
威廉希尔 初赔 2.10 3.20 3.50 最新 2.20 3.10 3.40
立博 初赔 2.00 3.25 3.60 当前 2.15 3.15 3.30
平均欧赔 2.05 3.22 3.45
"""
    with zipfile.ZipFile(pkg, "w") as zf:
        zf.writestr("odds.md", md)
    result = load_package(pkg)
    assert result.raw["match"]["home_team"] == "墨西哥"
    assert result.raw["match"]["away_team"] == "澳大利亚"
    assert {o["company"] for o in result.raw["odds"]} >= {"William", "Ladbrokes", "Avg"}
    assert any("更接近赔率包" in d.message for d in result.diagnostics)
