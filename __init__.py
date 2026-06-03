"""Shared contracts for the integrated FOCAS engine."""

from .enums import DECISIONS, OUTCOMES, PROMOTION_STATUSES
from .postmatch_schema import PostmatchSample, SchemaValidationError
from .prematch_schema import PrematchSnapshot
from .result_schema import ResultPayload

__all__ = [
    "OUTCOMES",
    "DECISIONS",
    "PROMOTION_STATUSES",
    "PostmatchSample",
    "PrematchSnapshot",
    "ResultPayload",
    "SchemaValidationError",
]
