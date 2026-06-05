import pytest

from focas_engine.models import CompanyOdds, OddsSnapshot
from focas_engine.motives import odds_moves
from focas_engine.odds_coordinate import build_odds_coordinates, coordinate_snapshot
from focas_engine.odds_system import build_odds_system_conversions


def _odds(company="William"):
    return [
        CompanyOdds(
            company=company,
            initial=OddsSnapshot(home=2.25, draw=3.20, away=3.00),
            current=OddsSnapshot(home=2.30, draw=3.10, away=3.10),
        )
    ]


def test_odds_coordinate_marks_non_low_items_as_reference(mini_table):
    conversions = build_odds_system_conversions(_odds())
    result = build_odds_coordinates(xlsx_path=mini_table, league="英超", conversions=conversions)
    assert len(result.company_sets) == 1
    coords = result.company_sets[0].coordinates
    assert len(coords) == 2
    assert any(c.time_point == "current" and c.is_snapshot_low for c in coords)
    assert all(c.evidence_level == "低赔骨架精确" for c in coords)
    assert all(c.conversion_status for c in coords)


def test_current_low_adapter_returns_legacy_table_result(mini_table):
    conversions = build_odds_system_conversions(_odds())
    result = build_odds_coordinates(xlsx_path=mini_table, league="英超", conversions=conversions)
    legacy = result.current_low_table_results("英超")
    assert len(legacy) == 1
    assert legacy[0].company == "William"
    assert legacy[0].direction in {"主低赔", "客低赔", "平低赔_特殊"}


def test_ladbrokes_uses_detected_system_sheet(mini_table):
    conversions = build_odds_system_conversions(_odds("Ladbrokes"))
    result = build_odds_coordinates(xlsx_path=mini_table, league="英超", conversions=conversions)
    low = result.company_sets[0].current_low_coordinate()
    assert low is not None
    assert low.lookup_status == "TABLE_READ_CONFIRMED"
    assert low.sheet_name == f"{low.system.removesuffix('系')}体系"
    assert low.evidence_level == "低赔骨架精确"


def test_table_lookup_requires_system_routing_metadata(mini_table):
    with pytest.raises(ValueError, match="TABLE_LOOKUP_FORBIDDEN"):
        coordinate_snapshot(
            xlsx_path=mini_table,
            league="英超",
            conversion=OddsSnapshot(home=2.0, draw=3.2, away=3.8),  # type: ignore[arg-type]
        )


def test_system_routing_preserves_published_odds(mini_table):
    conversions = build_odds_system_conversions(_odds())
    initial = conversions[0]
    assert initial.conversion_factor == 1.0
    assert initial.comparison_snapshot() == initial.raw_snapshot()
    assert initial.converted_snapshot() == initial.raw_snapshot()
    result = build_odds_coordinates(xlsx_path=mini_table, league="英超", conversions=conversions)
    opening = result.company_sets[0].coordinates[0]
    assert opening.odds_home == initial.raw_home
    assert opening.odds_draw == initial.raw_draw
    assert opening.odds_away == initial.raw_away


def test_cross_system_movement_uses_raw_institution_odds():
    odds = [
        CompanyOdds(
            company="William",
            initial=OddsSnapshot(home=2.10, draw=3.20, away=3.60),
            current=OddsSnapshot(home=2.20, draw=3.20, away=3.60),
        )
    ]
    routes = build_odds_system_conversions(odds)
    assert routes[0].target_system != routes[1].target_system
    home = next(move for move in odds_moves(odds, conversions=routes) if move.direction == "主胜")
    assert home.initial == pytest.approx(2.10)
    assert home.current == pytest.approx(2.20)
    assert home.delta == pytest.approx(0.10)
    assert home.comparison_basis == "raw_institution_odds"
