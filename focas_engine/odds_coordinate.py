from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .models import OddsSystemConversion, TableLookupResult
from .odds_system import conversion_map, normalize_company
from .returns import low_direction, low_odds
from .table_lookup import lookup_company_odds

LOW_SIDE_TO_DIRECTION = {"主低赔": "主胜", "客低赔": "客胜", "平低赔_特殊": "平局"}


@dataclass
class OddsCoordinate:
    company: str
    time_point: str
    direction: str
    raw_odds_value: float
    odds_value: float
    odds_home: float
    odds_draw: float
    odds_away: float
    actual_low_odds: float
    system: str
    return_rate: float
    snapshot_low_direction: str
    table_direction: str
    is_snapshot_low: bool
    interval_id: Optional[int]
    water_band: Optional[str]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    table_reference_odds: Optional[float]
    boundary_distance: Optional[float]
    deviation: str
    sheet_name: str
    row_number: Optional[int]
    lookup_status: str
    coordinate_status: str
    evidence_level: str
    conversion_status: str
    table_axis: str = "home"
    table_axis_odds: Optional[float] = None
    warnings: list[str] = field(default_factory=list)
    raw_row: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyCoordinateSet:
    company: str
    initial_system: str
    current_system: str
    initial_return_rate: float
    current_return_rate: float
    system_changed: bool
    coordinates: list[OddsCoordinate] = field(default_factory=list)

    def current_low_coordinate(self) -> OddsCoordinate | None:
        return next((item for item in self.coordinates if item.time_point == "current"), None)


@dataclass
class OddsCoordinateResult:
    company_sets: list[CompanyCoordinateSet] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def coordinates(self) -> list[OddsCoordinate]:
        return [coordinate for company_set in self.company_sets for coordinate in company_set.coordinates]

    def current_low_table_results(self, league: str = "") -> list[TableLookupResult]:
        results: list[TableLookupResult] = []
        for company_set in self.company_sets:
            coordinate = company_set.current_low_coordinate()
            if coordinate is None:
                continue
            results.append(TableLookupResult(
                company=coordinate.company,
                system=coordinate.system,
                league=league,
                direction=coordinate.table_direction,
                interval_id=coordinate.interval_id,
                water_band=coordinate.water_band,
                lower_bound=coordinate.lower_bound,
                upper_bound=coordinate.upper_bound,
                table_reference_odds=coordinate.table_reference_odds,
                actual_low_odds=coordinate.actual_low_odds,
                boundary_distance=coordinate.boundary_distance,
                deviation=coordinate.deviation,
                sheet_name=coordinate.sheet_name,
                row_number=coordinate.row_number,
                lookup_status=coordinate.lookup_status,
                table_axis=coordinate.table_axis,
                table_axis_odds=coordinate.table_axis_odds,
                raw_row=coordinate.raw_row,
            ))
        return results


def coordinate_snapshot(*, xlsx_path: str, league: str = "", conversion: OddsSystemConversion) -> list[OddsCoordinate]:
    if not isinstance(conversion, OddsSystemConversion):
        raise ValueError("TABLE_LOOKUP_FORBIDDEN: 坐标归位只能消费 odds_system 体系路由结果。")
    lookup = lookup_company_odds(
        xlsx_path=xlsx_path,
        league=league,
        company=normalize_company(conversion.company),
        conversion=conversion,
    )
    raw_snapshot = conversion.raw_snapshot()
    snapshot = conversion.comparison_snapshot()
    low_side = low_direction(snapshot)
    actual_low = low_odds(snapshot)
    direction = LOW_SIDE_TO_DIRECTION[low_side]
    return [OddsCoordinate(
        company=normalize_company(conversion.company),
        time_point=conversion.snapshot_type,
        direction=direction,
        raw_odds_value=float(low_odds(raw_snapshot)),
        odds_value=float(actual_low),
        odds_home=float(snapshot.home),
        odds_draw=float(snapshot.draw),
        odds_away=float(snapshot.away),
        actual_low_odds=float(actual_low),
        system=conversion.target_system,
        return_rate=round(conversion.raw_payout_percent, 4),
        snapshot_low_direction=low_side,
        table_direction=low_side,
        is_snapshot_low=True,
        interval_id=lookup.interval_id,
        water_band=lookup.water_band,
        lower_bound=lookup.lower_bound,
        upper_bound=lookup.upper_bound,
        table_reference_odds=lookup.table_reference_odds,
        boundary_distance=lookup.boundary_distance,
        deviation=lookup.deviation,
        sheet_name=lookup.sheet_name,
        row_number=lookup.row_number,
        lookup_status=lookup.lookup_status,
        coordinate_status="已按返还率体系读取低赔精确骨架；平赔与非低赔胜项仅作为组合参考。",
        evidence_level="低赔骨架精确",
        conversion_status=conversion.conversion_status,
        table_axis=lookup.table_axis,
        table_axis_odds=lookup.table_axis_odds,
        raw_row=lookup.raw_row,
    )]


def coordinate_company_conversions(
    *,
    xlsx_path: str,
    league: str = "",
    company: str,
    initial_conversion: OddsSystemConversion,
    current_conversion: OddsSystemConversion,
) -> CompanyCoordinateSet:
    coordinates: list[OddsCoordinate] = []
    for conversion in (initial_conversion, current_conversion):
        coordinates.extend(coordinate_snapshot(xlsx_path=xlsx_path, league=league, conversion=conversion))
    return CompanyCoordinateSet(
        company=normalize_company(company),
        initial_system=initial_conversion.target_system,
        current_system=current_conversion.target_system,
        initial_return_rate=round(initial_conversion.raw_payout_percent, 4),
        current_return_rate=round(current_conversion.raw_payout_percent, 4),
        system_changed=initial_conversion.target_system != current_conversion.target_system,
        coordinates=coordinates,
    )


def build_odds_coordinates(
    *,
    xlsx_path: str,
    conversions: list[OddsSystemConversion],
    league: str = "",
) -> OddsCoordinateResult:
    result = OddsCoordinateResult()
    by_key = conversion_map(conversions)
    companies = sorted({normalize_company(item.company) for item in conversions})
    for company in companies:
        initial = by_key.get((company, "initial"))
        current = by_key.get((company, "current"))
        if initial is None or current is None:
            result.notes.append(f"{company} 缺少完整初赔/即时赔返还率体系路由，TABLE_LOOKUP_FORBIDDEN。")
            continue
        if initial.system_lookup_status != "SYSTEM_LOOKUP_ALLOWED" or current.system_lookup_status != "SYSTEM_LOOKUP_ALLOWED":
            result.notes.append(f"{company} 返还率体系不可调用，TABLE_LOOKUP_FORBIDDEN。")
            continue
        result.company_sets.append(coordinate_company_conversions(
            xlsx_path=xlsx_path,
            league=league,
            company=company,
            initial_conversion=initial,
            current_conversion=current,
        ))
    for company_set in result.company_sets:
        current = company_set.current_low_coordinate()
        if current is None or current.lookup_status != "TABLE_READ_CONFIRMED":
            result.notes.append(f"{company_set.company} 当前赔率未完成新版现代骨架归位。")
        if company_set.system_changed:
            result.notes.append(
                f"{company_set.company} 初赔体系 {company_set.initial_system} → 当前体系 {company_set.current_system}，按各自实际返还率体系分别查表。"
            )
    if league:
        result.notes.append(f"赛事语境={league}；仅参与语义修正，不作为现代骨架查表准入条件。")
    return result
