from __future__ import annotations

from pathlib import Path

HARD_DATA_SOURCE = "FOCAS_89_96_MODERN_SKELETON_INTERVAL_COMPACT_v5_CORRECTED_MARKET_LADDER.xlsx"
LEGACY_HARD_DATA_SOURCES = {
    "FOCAS_P1_89_96_LOW_MID_HIGH_FULL_CALIBRATED_v1_中文版.xlsx",
    "FOCAS_89_96_MODERN_SKELETON_INTERVAL_COMPACT_v5_ANALYSIS_READY.xlsx",
}
SYSTEM_DISTANCE_TOLERANCE = 0.5


def resolve_table_path(table_path: str | Path | None) -> Path:
    return Path(table_path or HARD_DATA_SOURCE).resolve()


def is_legacy_hard_data_source(table_path: str | Path) -> bool:
    return Path(table_path).name in LEGACY_HARD_DATA_SOURCES
