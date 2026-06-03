from pathlib import Path
import zipfile

from focas_engine.match_package_loader import load_package


def test_zgzcw_debug_text_fallback_reads_william_ladbrokes(tmp_path: Path):
    pkg = tmp_path / "pkg.zip"
    with zipfile.ZipFile(pkg, "w") as z:
        z.writestr(
            "4468109/match_metadata.csv",
            "source_provider,source_match_id,league,season,match_date,home_team,away_team,bjop_url\n"
            "ZGZCW,4468109,芬超,UNK,2026-05-31,奥卢,雅罗,url\n",
        )
        z.writestr(
            "4468109/opening_closing.csv",
            "source_provider,source_match_id,target_company,opening_home,opening_draw,opening_away,closing_home,closing_draw,closing_away\n",
        )
        z.writestr(
            "4468109/debug/William_Source_zhishu_text.txt",
            "当前位置：足彩网> 赛事中心>芬超 2026> 奥卢 VS 雅罗\n"
            "威*指数变化\n"
            "1\t2026-05-31 14:24:22\n赛前6时35分\n\t1.67↑\t3.70↓\t4.60↓\t55.11\n"
            "2\t2026-05-24 22:13:45\n赛前166时46分\n\t1.67\t3.60\t4.50\t54.50\n",
        )
        z.writestr(
            "4468109/debug/Ladbrokes_Source_zhishu_text.txt",
            "当前位置：足彩网> 赛事中心>芬超 2026> 奥卢 VS 雅罗\n"
            "立*指数变化\n"
            "1\t2026-05-31 14:22:30\n赛前6时37分\n\t1.65↑\t3.50↓\t4.40↓\t54.16\n"
            "2\t2026-05-25 18:02:32\n赛前146时57分\n\t1.55\t3.80\t4.80\t57.78\n",
        )
    result = load_package(pkg)
    by_company = {o["company"]: o for o in result.raw["odds"]}
    assert by_company["William"]["initial"] == {"home": 1.67, "draw": 3.6, "away": 4.5}
    assert by_company["William"]["current"] == {"home": 1.67, "draw": 3.7, "away": 4.6}
    assert by_company["Ladbrokes"]["initial"] == {"home": 1.55, "draw": 3.8, "away": 4.8}
    assert by_company["Ladbrokes"]["current"] == {"home": 1.65, "draw": 3.5, "away": 4.4}
