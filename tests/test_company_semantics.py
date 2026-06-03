from focas_engine.company_semantics import analyze_company_semantics
from focas_engine.models import MotiveReading, OddsMove


def test_company_semantics_mainline_double_confirmation():
    moves = [
        OddsMove("William", "主胜", 2.2, 2.15, -0.05, "压低"),
        OddsMove("Ladbrokes", "主胜", 2.25, 2.18, -0.07, "压低"),
    ]
    motives = [
        MotiveReading("William", "主胜", "压低", "强", "足", "中", "主线承接 / 真实保护", "test", False),
        MotiveReading("Ladbrokes", "主胜", "压低", "强", "足", "中", "主线承接 / 真实保护", "test", False),
    ]
    r = analyze_company_semantics(moves=moves, motive_readings=motives, p1_core=None)
    assert r.relation_type == "同向确认"
    assert "主胜" in r.confirmed_directions
    assert "主胜" in r.mainline_confirmed_directions


def test_odds_raise_carry_boundary_is_not_mainline_confirmation():
    moves = [
        OddsMove("William", "主胜", 2.2, 2.3, 0.10, "抬高"),
        OddsMove("Ladbrokes", "主胜", 2.25, 2.35, 0.10, "抬高"),
    ]
    motives = [
        MotiveReading("William", "主胜", "抬高", "强", "足", "中", "顶高承接边界 / 未打掉信心备选", "抬高不是给信心", False),
        MotiveReading("Ladbrokes", "主胜", "抬高", "强", "足", "中", "顶高承接边界 / 未打掉信心备选", "抬高不是给信心", False),
    ]
    r = analyze_company_semantics(moves=moves, motive_readings=motives, p1_core=None)
    assert r.relation_type == "未确认"
    assert "主胜" not in r.confirmed_directions
    assert "主胜" not in r.mainline_confirmed_directions
    assert any("不计为机构给信心" in e for reading in r.readings for e in reading.evidence)


def test_risk_repair_not_promoted_to_mainline_confirmation():
    moves = [
        OddsMove("William", "平局", 3.3, 3.1, -0.2, "压低"),
        OddsMove("Ladbrokes", "平局", 3.4, 3.2, -0.2, "压低"),
    ]
    motives = [
        MotiveReading("William", "平局", "压低", "中", "中", "中", "保护 / 风险修正备选", "test", False),
        MotiveReading("Ladbrokes", "平局", "压低", "中", "中", "中", "保护 / 风险修正备选", "test", False),
    ]
    r = analyze_company_semantics(moves=moves, motive_readings=motives, p1_core=None)
    assert r.relation_type == "同向确认"
    assert "平局" in r.risk_repair_directions
    assert "平局" not in r.confirmed_directions


def test_company_semantics_single_company_not_confirmation():
    moves = [
        OddsMove("William", "平局", 3.3, 3.1, -0.2, "压低"),
        OddsMove("Ladbrokes", "主胜", 2.0, 2.0, 0.0, "稳定"),
    ]
    motives = [
        MotiveReading("William", "平局", "压低", "中", "中", "中", "保护 / 风险修正备选", "test", False),
    ]
    r = analyze_company_semantics(moves=moves, motive_readings=motives, p1_core=None)
    assert r.relation_type == "未确认"
    assert "平局" in r.unconfirmed_directions
    assert "平局" not in r.confirmed_directions


def test_avg_is_background_only():
    moves = [OddsMove("Avg", "客胜", 3.0, 2.8, -0.2, "压低")]
    motives = [MotiveReading("Avg", "客胜", "压低", "强", "足", "中", "保护 / 风险修正备选", "test", False)]
    r = analyze_company_semantics(moves=moves, motive_readings=motives, p1_core=None)
    assert r.readings[0].company == "市场平均"
    assert r.readings[0].confirmation_level == "背景参考"
    assert not r.confirmed_directions


def test_stable_motive_is_not_mainline_confirmation():
    moves = [
        OddsMove("William", "客胜", 3.2, 3.2, 0.0, "稳定"),
        OddsMove("Ladbrokes", "客胜", 3.1, 3.1, 0.0, "稳定"),
    ]
    motives = [
        MotiveReading("William", "客胜", "稳定", "中", "维持原承载", "未新增分散动作", "维持承接", "test", False),
        MotiveReading("Ladbrokes", "客胜", "稳定", "中", "维持原承载", "未新增分散动作", "维持承接", "test", False),
    ]
    r = analyze_company_semantics(moves=moves, motive_readings=motives, p1_core=None)
    assert r.relation_type == "未确认"
    assert "客胜" not in r.confirmed_directions
