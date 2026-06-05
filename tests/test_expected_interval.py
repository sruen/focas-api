from focas_engine.expected_interval import expected_interval_from_gap, expected_interval_from_table, parse_gap_value
from focas_engine.models import StrengthContext


def test_parse_half_away_gap_from_manual_strength():
    strength = StrengthContext(
        home_grade="中下",
        away_grade="中游",
        static_gap="客高0.5档",
        dynamic_adjustment="主场回补后仍客高0.5档",
        final_gap="客高0.5档",
        original_distribution="客向浅优势",
    )
    assert parse_gap_value(strength, None) == -0.5


def test_explicit_numeric_gap_wins_over_later_near_same_grade_description():
    strength = StrengthContext(
        home_grade="中下",
        away_grade="中游",
        static_gap="客队高约0.5档",
        dynamic_adjustment="",
        final_gap="客队高0.5档；动态后接近同档，客队仍略高",
    )
    assert parse_gap_value(strength, None) == -0.5


def test_away_half_grade_maps_to_expected_interval_one():
    expected = expected_interval_from_gap(-0.5)
    assert expected.expected_low_side == "客低赔"
    assert expected.expected_interval_id == 1
    assert expected.expected_interval_source == "RULE_FALLBACK"
    assert "每0.5档移动一个骨架区间" in "".join(expected.notes)


def test_formal_expected_interval_comes_from_table():
    strength = StrengthContext(
        home_grade="中上",
        away_grade="中游",
        static_gap="主队高一档",
        dynamic_adjustment="维持",
        final_gap="主队高一档",
    )
    expected = expected_interval_from_table(strength=strength)
    assert expected.expected_interval_source == "STRENGTH_INTERVAL_BRIDGE"
    assert expected.lookup_key_status == "TABLE_MATCHED"
    assert expected.matched_sheet == "focas_engine/data/p4_strength_interval_table.csv"


def test_formal_away_two_grade_maps_to_away_low_skeleton_bridge():
    strength = StrengthContext(
        home_grade="下游",
        away_grade="中强",
        static_gap="客队高两档",
        dynamic_adjustment="维持",
        final_gap="客队高两档",
    )
    expected = expected_interval_from_table(strength=strength)
    assert expected.p4_strength_key == "gap:-2.0"
    assert expected.expected_low_side == "客低赔"
    assert expected.expected_interval_id == 0
    assert expected.expected_water_band == "高水"


def test_formal_home_one_grade_maps_to_interval_four_with_half_grade_scale():
    strength = StrengthContext(
        home_grade="普强",
        away_grade="中强",
        static_gap="主队高一档",
        dynamic_adjustment="维持",
        final_gap="主队高一档",
    )
    expected = expected_interval_from_table(strength=strength)
    assert expected.p4_strength_key == "gap:1.0"
    assert expected.expected_low_side == "主低赔"
    assert expected.expected_interval_id == 4
