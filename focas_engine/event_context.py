from __future__ import annotations

from .models import MatchContext


KNOCKOUT_CONTEXT_KEYWORDS = ("决赛", "半决赛", "淘汰", "杯")


def is_knockout_like_context(match: MatchContext) -> bool:
    """Return whether a single-match flag belongs to a cup or knockout context."""
    text = " ".join(
        str(value)
        for value in (match.competition, match.stage, match.match_type)
        if value
    )
    return any(keyword in text for keyword in KNOCKOUT_CONTEXT_KEYWORDS)
