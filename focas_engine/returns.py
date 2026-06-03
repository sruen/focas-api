from __future__ import annotations

from .models import OddsSnapshot


def payout_rate(snapshot: OddsSnapshot) -> float:
    """European odds return rate, e.g. 94.2 means 94系."""
    implied = (1.0 / snapshot.home) + (1.0 / snapshot.draw) + (1.0 / snapshot.away)
    return 100.0 / implied


def system_from_snapshot(snapshot: OddsSnapshot) -> str:
    rate = payout_rate(snapshot)
    rounded = int(round(rate))
    if 89 <= rounded <= 96:
        return f"{rounded}系"
    if rounded < 89:
        return "低于89系"
    return "高于96系"


def low_direction(snapshot: OddsSnapshot) -> str:
    """The table uses 主低赔/客低赔. Draw-low cases are structurally special and flagged."""
    if snapshot.draw < snapshot.home and snapshot.draw < snapshot.away:
        return "平低赔_特殊"
    return "主低赔" if snapshot.home <= snapshot.away else "客低赔"


def low_odds(snapshot: OddsSnapshot) -> float:
    d = low_direction(snapshot)
    if d == "主低赔":
        return snapshot.home
    if d == "客低赔":
        return snapshot.away
    return snapshot.draw
