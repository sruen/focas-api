from __future__ import annotations

from .models import CompanyOdds, OddsSnapshot, OddsSystemConversion
from .returns import payout_rate
from .config import SYSTEM_DISTANCE_TOLERANCE

AVAILABLE_SYSTEMS = tuple(range(89, 97))
HARD_COMPANIES = {"William", "威廉", "Ladbrokes", "Lad", "立博"}
COMPANY_ALIASES = {
    "william": "William",
    "威廉": "William",
    "ladbrokes": "Ladbrokes",
    "lad": "Ladbrokes",
    "立博": "Ladbrokes",
    "avg": "Avg",
    "average": "Avg",
    "市场平均": "Avg",
}


def normalize_company(company: str) -> str:
    return COMPANY_ALIASES.get(company.strip().lower(), company)


def detect_nearest_available_system(payout_percent: float) -> tuple[str, float, str]:
    nearest = min(AVAILABLE_SYSTEMS, key=lambda system: (abs(system - payout_percent), system))
    distance = round(abs(nearest - payout_percent), 6)
    if payout_percent < AVAILABLE_SYSTEMS[0] or payout_percent > AVAILABLE_SYSTEMS[-1]:
        status = "OUTSIDE_89_96_NEAREST_BOUNDARY"
    elif distance <= 0.005:
        status = "EXACT_SYSTEM"
    else:
        status = "NEAREST_AVAILABLE_SYSTEM"
    return f"{nearest}系", distance, status


def route_snapshot_to_system(
    *,
    company: str,
    snapshot_type: str,
    snapshot: OddsSnapshot,
) -> OddsSystemConversion:
    """Route published odds to the matching skeleton sheet without changing values.

    The 89-96 return-rate adjustment is already represented by the workbook's
    system-specific sheets. Multiplying the institution odds again would apply
    the adjustment twice.
    """
    raw_payout = payout_rate(snapshot)
    detected, distance, match_status = detect_nearest_available_system(raw_payout)
    lookup_allowed = distance <= SYSTEM_DISTANCE_TOLERANCE
    if not lookup_allowed:
        conversion_status = "SYSTEM_LOOKUP_FORBIDDEN"
        system_lookup_status = "SYSTEM_DISTANCE_EXCEEDED"
    else:
        conversion_status = "RAW_ODDS_PRESERVED_SYSTEM_TABLE_ROUTING"
        system_lookup_status = "SYSTEM_LOOKUP_ALLOWED"
    return OddsSystemConversion(
        company=normalize_company(company),
        snapshot_type=snapshot_type,
        raw_home=float(snapshot.home),
        raw_draw=float(snapshot.draw),
        raw_away=float(snapshot.away),
        raw_payout_percent=round(raw_payout, 6),
        detected_system=detected,
        system_distance=distance,
        system_match_status=match_status,
        target_system=detected,
        # Compatibility fields only. System-specific adjustment lives in xlsx.
        conversion_factor=1.0,
        converted_home=float(snapshot.home),
        converted_draw=float(snapshot.draw),
        converted_away=float(snapshot.away),
        conversion_status=conversion_status,
        system_lookup_status=system_lookup_status,
        odds_type=snapshot_type,
        odds_home=float(snapshot.home),
        odds_draw=float(snapshot.draw),
        odds_away=float(snapshot.away),
        calculated_return_rate=round(raw_payout, 6),
    )


def convert_snapshot_to_system(
    *,
    company: str,
    snapshot_type: str,
    snapshot: OddsSnapshot,
) -> OddsSystemConversion:
    """Backward-compatible alias for system-sheet routing."""
    return route_snapshot_to_system(company=company, snapshot_type=snapshot_type, snapshot=snapshot)


def build_odds_system_routes(odds: list[CompanyOdds]) -> list[OddsSystemConversion]:
    routes: list[OddsSystemConversion] = []
    for company_odds in odds:
        routes.append(
            route_snapshot_to_system(
                company=company_odds.company,
                snapshot_type="initial",
                snapshot=company_odds.initial,
            )
        )
        routes.append(
            route_snapshot_to_system(
                company=company_odds.company,
                snapshot_type="current",
                snapshot=company_odds.current,
            )
        )
    return routes


def build_odds_system_conversions(odds: list[CompanyOdds]) -> list[OddsSystemConversion]:
    """Backward-compatible alias for building system-sheet routes."""
    return build_odds_system_routes(odds)


def conversion_map(conversions: list[OddsSystemConversion]) -> dict[tuple[str, str], OddsSystemConversion]:
    return {(normalize_company(item.company), item.snapshot_type): item for item in conversions}


def require_hard_company_conversions(conversions: list[OddsSystemConversion]) -> tuple[bool, list[str]]:
    by_key = conversion_map(conversions)
    missing = [
        f"{company} {snapshot_type} 返还率体系路由"
        for company in ("William", "Ladbrokes")
        for snapshot_type in ("initial", "current")
        if (company, snapshot_type) not in by_key
    ]
    missing.extend(
        f"{company} {snapshot_type} 返还率体系不可调用：{by_key[(company, snapshot_type)].system_lookup_status}"
        for company in ("William", "Ladbrokes")
        for snapshot_type in ("initial", "current")
        if (company, snapshot_type) in by_key
        and by_key[(company, snapshot_type)].system_lookup_status != "SYSTEM_LOOKUP_ALLOWED"
    )
    return not missing, missing
