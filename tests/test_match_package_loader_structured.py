import zipfile
from pathlib import Path

from focas_engine.match_package_loader import load_package


def test_structured_zgzcw_csv_package(tmp_path: Path):
    pkg = tmp_path / "pkg.zip"
    with zipfile.ZipFile(pkg, "w") as z:
        z.writestr(
            "4512487/match_metadata.csv",
            "source_provider,source_match_id,league,season,match_date,home_team,away_team,bjop_url\n"
            "ZGZCW,4512487,国际友谊,UNK,2026-05-30,墨西哥,澳大利亚,url\n",
        )
        z.writestr(
            "4512487/opening_closing.csv",
            "source_provider,source_match_id,league,season,match_date,home_team,away_team,target_company,company_name_raw,company_id,opening_time_raw,opening_datetime_full,opening_home,opening_draw,opening_away,closing_time_raw,closing_datetime_full,closing_home,closing_draw,closing_away,record_count,move_available,data_quality_flag\n"
            "ZGZCW,4512487,国际友谊,UNK,2026-05-30,墨西哥,澳大利亚,William_Source,威*,9,t,t,1.57,3.80,5.00,t,t,1.60,3.70,5.00,14,YES,OK\n"
            "ZGZCW,4512487,国际友谊,UNK,2026-05-30,墨西哥,澳大利亚,Ladbrokes_Source,立*,5,t,t,1.55,4.20,5.50,t,t,1.61,3.90,5.25,11,YES,OK\n"
            "ZGZCW,4512487,国际友谊,UNK,2026-05-30,墨西哥,澳大利亚,BetVictor_Source,韦*,11,t,t,1.60,3.70,5.00,t,t,1.57,3.75,5.25,11,YES,OK\n",
        )
        z.writestr(
            "4512487/debug/bjop_page_text.txt",
            "当前位置：足彩网> 赛事中心>国际友谊 2026> 墨西哥 VS 澳大利亚\n"
            "比赛时间：2026-05-31 10:00:00\n球场：中立场\n"
            "平均欧赔 1.78 3.45 4.20 1.59 3.83 5.11 57.93 24.05 18.02\n",
        )
    result = load_package(pkg)
    raw = result.raw
    assert raw["match"]["home_team"] == "墨西哥"
    assert raw["match"]["away_team"] == "澳大利亚"
    by_company = {o["company"]: o for o in raw["odds"]}
    assert by_company["William"]["initial"] == {"home": 1.57, "draw": 3.8, "away": 5.0}
    assert by_company["William"]["current"] == {"home": 1.6, "draw": 3.7, "away": 5.0}
    assert by_company["Ladbrokes"]["initial"] == {"home": 1.55, "draw": 4.2, "away": 5.5}
    assert by_company["Ladbrokes"]["current"] == {"home": 1.61, "draw": 3.9, "away": 5.25}
    assert by_company["Avg"]["initial"] == {"home": 1.78, "draw": 3.45, "away": 4.2}
    assert by_company["Avg"]["current"] == {"home": 1.59, "draw": 3.83, "away": 5.11}
    assert by_company["BetVictor"]["initial"] == {"home": 1.6, "draw": 3.7, "away": 5.0}
    assert by_company["BetVictor"]["current"] == {"home": 1.57, "draw": 3.75, "away": 5.25}
