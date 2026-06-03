"""Shared enum-like constants."""

OUTCOMES = frozenset({"胜", "平", "负"})
DECISIONS = frozenset({*OUTCOMES, "PASS"})
PROMOTION_STATUSES = frozenset({"candidate", "watch", "usable", "rule_candidate", "rejected"})

PREMATCH_TO_OUTCOME = {
    "主胜": "胜",
    "平局": "平",
    "客胜": "负",
    "胜": "胜",
    "平": "平",
    "负": "负",
    "PASS": "PASS",
}

OUTCOME_TO_PREMATCH = {
    "胜": "主胜",
    "平": "平局",
    "负": "客胜",
}
