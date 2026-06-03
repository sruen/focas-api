from __future__ import annotations

from .models import DirectionJudgement, IntegratedStructureJudgement, MotiveReading, TableLookupResult

DIRECTIONS = ("主胜", "平局", "客胜")


def judge_directions(
    *,
    integrated_structure: IntegratedStructureJudgement | None = None,
    motive_readings: list[MotiveReading] | None = None,
    table_results: list[TableLookupResult] | None = None,
    interval_audit=None,
) -> list[DirectionJudgement]:
    """Compatibility adapter for callers that previously used the old state table.

    Stage 10 now owns directional judgement. Motive readings, table rows or
    interval tags are insufficient on their own because they omit part of the
    required reasoning chain.
    """
    if integrated_structure is not None:
        return list(integrated_structure.summary_status)
    return [
        DirectionJudgement(
            direction,
            "未确认",
            ["未运行 Stage 10 综合结构判断；动作、查表或区间标签不能单独生成不利排除。"],
        )
        for direction in DIRECTIONS
    ]


def select_final_direction(judgements: list[DirectionJudgement]) -> tuple[str | None, str]:
    adverse = [item.direction for item in judgements if item.status == "不利"]
    remaining = [item.direction for item in judgements if item.direction not in adverse]
    if len(adverse) == 2 and len(remaining) == 1:
        return remaining[0], f"两个方向经 Stage 10 完整证据链排除，剩余 {remaining[0]} 为结构主线。"
    if len(adverse) == 0:
        return None, "NO_MAINLINE：Stage 10 未形成两个明确不利方向，进入第二阶段相对主线选择。"
    if len(adverse) == 3:
        return None, "NO_BETTER_STRUCTURE：三项均形成不利处理，赔面冲突，暂停。"
    return None, "SECOND_STAGE_REQUIRED：仅形成一个明确不利方向，进入第二阶段相对主线选择。"
