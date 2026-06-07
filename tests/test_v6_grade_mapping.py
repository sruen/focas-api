import openpyxl

from focas_engine.expected_interval import expected_interval_from_table
from focas_engine.models import StrengthContext


def test_v6_grade_mapping_routes_strength_grades_to_interval(tmp_path):
    path = tmp_path / "v6.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "\u6863\u6b21\u6620\u5c04"
    sheet.append(["\u4e3b\u961f\u2193  \u5ba2\u961f\u2192", "\u4eba\u5f3a", "\u666e\u5f3a", "\u51c6\u5f3a", "\u4e2d\u5f3a"])
    sheet.append(["\u666e\u5f3a", "0-1\u533a", "1\u533a", "2-3\u533a", "5\u533a"])
    workbook.save(path)

    strength = StrengthContext(
        home_grade="\u666e\u5f3a",
        away_grade="\u4e2d\u5f3a",
        final_gap="\u4e3b\u961f\u9ad81\u6863",
    )

    expected = expected_interval_from_table(strength=strength, table_path=path)

    assert expected.lookup_key_status == "V6_GRADE_MAP_MATCHED"
    assert expected.expected_interval_id == 5
    assert expected.expected_low_side == "\u4e3b\u4f4e\u8d54"
    assert "\u6863\u6b21\u6620\u5c04" in expected.matched_sheet


def test_v6_grade_mapping_keeps_interval_range(tmp_path):
    path = tmp_path / "v6.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "\u6863\u6b21\u6620\u5c04"
    sheet.append(["\u4e3b\u961f\u2193  \u5ba2\u961f\u2192", "\u4eba\u5f3a", "\u666e\u5f3a", "\u51c6\u5f3a"])
    sheet.append(["\u666e\u5f3a", "0-1\u533a", "1\u533a", "2-3\u533a"])
    workbook.save(path)

    strength = StrengthContext(
        home_grade="\u666e\u5f3a",
        away_grade="\u51c6\u5f3a",
        final_gap="\u4e3b\u961f\u9ad80.5\u6863",
    )

    expected = expected_interval_from_table(strength=strength, table_path=path)

    assert expected.lookup_key_status == "V6_GRADE_MAP_MATCHED"
    assert expected.expected_interval_id == 2
    assert expected.expected_interval_min_id == 2
    assert expected.expected_interval_max_id == 3
    assert expected.expected_interval_raw_zone == "2-3\u533a"
    assert expected.expected_interval_range_status == "RANGE_INTERVAL"
    assert expected.callable_interval_ids == [2, 3]
