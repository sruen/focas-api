from __future__ import annotations

import json
import zipfile
from pathlib import Path

from focas_engine.io import load_input_with_report
from focas_engine.match_package_loader import load_package


def test_package_loader_uses_canonical_json(tmp_path: Path):
    raw = json.loads(Path('examples/valid_complete_match_input.json').read_text(encoding='utf-8'))
    raw['match']['home_team'] = '巴黎圣日耳曼'
    raw['match']['away_team'] = '阿森纳'
    pkg = tmp_path / 'pkg.zip'
    with zipfile.ZipFile(pkg, 'w') as zf:
        zf.writestr('match_input.json', json.dumps(raw, ensure_ascii=False))
    loaded = load_input_with_report(pkg)
    assert loaded.match.home_team == '巴黎圣日耳曼'
    assert loaded.match.away_team == '阿森纳'
    assert any('标准JSON' in d.message for d in loaded.diagnostics)
    assert len(loaded.odds) == 3


def test_package_loader_extracts_text_odds_and_exports_partial_raw(tmp_path: Path):
    text = '''
比赛：墨西哥 VS 澳大利亚
赛事：友谊赛
比赛时间：2026-06-01 20:00
中立场
William 初赔 2.10/3.20/3.50
William 最新 2.20/3.10/3.40
Ladbrokes 初赔 2.00/3.25/3.60
Ladbrokes 最新 2.15/3.15/3.30
Avg 2.05/3.22/3.45
'''
    pkg = tmp_path / 'text_pkg.zip'
    with zipfile.ZipFile(pkg, 'w') as zf:
        zf.writestr('odds.md', text)
    res = load_package(pkg)
    assert res.raw['match']['home_team'] == '墨西哥'
    assert res.raw['match']['away_team'] == '澳大利亚'
    companies = {o['company'] for o in res.raw['odds']}
    assert {'William', 'Ladbrokes', 'Avg'} <= companies
    william = next(o for o in res.raw['odds'] if o['company'] == 'William')
    assert william['initial']['home'] == 2.10
    assert william['current']['home'] == 2.20
    assert any('部分标准输入' in d.message for d in res.diagnostics)


def test_package_loader_rejects_zip_path_traversal(tmp_path: Path):
    pkg = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(pkg, 'w') as zf:
        zf.writestr('../escaped.json', '{}')
    try:
        load_package(pkg)
    except ValueError as exc:
        assert 'ZIP_UNSAFE_PATH' in str(exc)
    else:
        raise AssertionError('path traversal zip must be rejected')
