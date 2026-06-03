from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from . import __version__
from .models import MatchContext, PipelineResult

DIRECTION_ALIASES = {
    "H": "主胜",
    "HOME": "主胜",
    "HOME_WIN": "主胜",
    "主": "主胜",
    "胜": "主胜",
    "主胜": "主胜",
    "1": "主胜",
    "D": "平局",
    "DRAW": "平局",
    "平": "平局",
    "平局": "平局",
    "X": "平局",
    "0": "平局",
    "A": "客胜",
    "AWAY": "客胜",
    "AWAY_WIN": "客胜",
    "负": "客胜",
    "客": "客胜",
    "客胜": "客胜",
    "2": "客胜",
}


@dataclass
class OOSRecord:
    """One out-of-sample validation record.

    This record is intentionally compact: it stores enough information to audit
    the pre-match chain without preserving the whole pipeline payload. It should
    be appended to a JSONL ledger after the actual result is known.
    """

    home_team: str
    away_team: str
    competition: Optional[str]
    kickoff_time: Optional[str]
    engine_version: str = __version__
    created_at: Optional[str] = None
    match_id: Optional[str] = None
    input_hash: Optional[str] = None
    table_hash: Optional[str] = None
    predicted_direction: Optional[str] = None
    actual_direction: Optional[str] = None
    hit: Optional[bool] = None
    status: str = ""
    failure_bucket: Optional[str] = None
    failure_reasons: list[str] = field(default_factory=list)
    adverse_exclusions: list[str] = field(default_factory=list)
    relative_non_selected: list[str] = field(default_factory=list)
    direction_statuses: dict[str, str] = field(default_factory=dict)
    final_selection_method: Optional[str] = None
    final_confidence: Optional[str] = None
    company_relation: Optional[str] = None
    p1_distribution_type: Optional[str] = None
    stop_reason: Optional[str] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class OOSSummary:
    total: int
    evaluated: int
    hits: int
    misses: int
    hit_rate: Optional[float]
    by_failure_bucket: dict[str, int] = field(default_factory=dict)




def sha256_file(path: str | Path | None) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def default_match_id(match: MatchContext) -> str:
    parts = [match.kickoff_time or "unknown_time", match.competition or "unknown_comp", match.home_team, match.away_team]
    return "|".join(str(x) for x in parts)


def normalize_direction(value: str | None) -> Optional[str]:
    if value is None:
        return None
    key = str(value).strip().upper()
    # Chinese values are not affected by upper(), but this keeps English aliases stable.
    if key in DIRECTION_ALIASES:
        return DIRECTION_ALIASES[key]
    raw = str(value).strip()
    return DIRECTION_ALIASES.get(raw, None)


def direction_from_score(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "主胜"
    if home_goals == away_goals:
        return "平局"
    return "客胜"


def parse_score(score: str) -> tuple[int, int]:
    """Parse common score formats: '2-1', '2:1', '2：1'."""
    s = score.strip().replace("：", ":").replace("-", ":")
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError("score must look like '2-1' or '2:1'")
    return int(parts[0]), int(parts[1])


def _direction_statuses(result: PipelineResult) -> dict[str, str]:
    return {j.direction: j.status for j in result.direction_judgements}


def _relative_parts(result: PipelineResult) -> tuple[list[str], list[str], Optional[str], Optional[str]]:
    if not result.relative_selection:
        adverse = [j.direction for j in result.direction_judgements if j.status == "不利"]
        return adverse, [], None, None
    r = result.relative_selection
    return list(r.adverse_exclusions), list(r.relative_non_selected), r.method, r.confidence


def classify_oos_miss(result: PipelineResult, actual_direction: Optional[str]) -> tuple[Optional[str], list[str]]:
    """Classify misses without using the actual result to rewrite the original logic.

    Buckets are intentionally coarse. They are for audit/backtesting, not for
    automatically upgrading rules from one match.
    """
    reasons: list[str] = []
    if result.stop:
        return "NOT_EVALUATED_STOP", ["赛前流程已暂停，不能把该场纳入命中/错因统计。"]
    if actual_direction is None:
        return "ACTUAL_RESULT_MISSING", ["缺少实际赛果方向。"]
    if result.final_direction in {None, "PASS"}:
        return "NO_PREMATCH_DIRECTION", ["赛前未形成结构方向。"]

    adverse_exclusions, relative_non_selected, _, _ = _relative_parts(result)
    statuses = _direction_statuses(result)

    if actual_direction in adverse_exclusions or statuses.get(actual_direction) == "不利":
        reasons.append("实际方向在赛前被明确不利排除，优先检查 Stage 10 综合结构判断、原始分布、Stage 8 坐标归位和 Stage 9 公司动机链。")
        return "ADVERSE_EXCLUSION_ERROR", reasons

    if actual_direction in relative_non_selected:
        reasons.append("实际方向赛前未被不利排除，只是在第二阶段相对选择中落选，优先检查相对主线选择权重。")
        return "RELATIVE_SELECTION_ERROR", reasons

    if result.company_semantics and "冲突" in result.company_semantics.relation_type:
        reasons.append("公司语义层存在冲突，赛前可能低估了公司分歧对主线稳定性的破坏。")
        return "COMPANY_CONFLICT_UNDERWEIGHTED", reasons

    if result.odds_coordinates and result.odds_coordinates.notes:
        reasons.append("Stage 8 坐标层存在备注或警告，需检查返还率体系路由、骨架表匹配、非低赔参考和当前低赔确认是否过度使用。")
        return "STAGE_8_COORDINATE_REVIEW", reasons

    reasons.append("实际方向不属于明确不利排除或相对未选中，归为主线选择综合误差。")
    return "MAINLINE_SELECTION_ERROR", reasons


def build_oos_record(
    *,
    match: MatchContext,
    result: PipelineResult,
    actual_direction: str | None = None,
    score: str | None = None,
    input_path: str | Path | None = None,
    table_path: str | Path | None = None,
    match_id: str | None = None,
) -> OOSRecord:
    if score and not actual_direction:
        actual_direction = direction_from_score(*parse_score(score))
    actual = normalize_direction(actual_direction)
    predicted = normalize_direction(result.final_direction)

    adverse_exclusions, relative_non_selected, method, confidence = _relative_parts(result)

    if result.stop:
        hit = None
        status = "NOT_EVALUATED_STOP"
        bucket = "NOT_EVALUATED_STOP"
        reasons = ["赛前流程暂停：不进入赛后命中/错因统计。"]
    elif actual is None:
        hit = None
        status = "ACTUAL_RESULT_MISSING"
        bucket = "ACTUAL_RESULT_MISSING"
        reasons = ["缺少实际赛果方向。"]
    elif predicted is None:
        hit = None
        status = "NO_PREMATCH_DIRECTION"
        bucket = "NO_PREMATCH_DIRECTION"
        reasons = ["赛前未形成结构方向。"]
    elif predicted == actual:
        hit = True
        status = "HIT"
        bucket = None
        reasons = ["赛前结构方向与实际方向一致。"]
    else:
        hit = False
        status = "MISS"
        bucket, reasons = classify_oos_miss(result, actual)

    company_relation = result.company_semantics.relation_type if result.company_semantics else None
    p1_distribution = result.p1_core.distribution_type if result.p1_core else None

    return OOSRecord(
        home_team=match.home_team,
        away_team=match.away_team,
        competition=match.competition,
        kickoff_time=match.kickoff_time,
        engine_version=__version__,
        created_at=datetime.now(timezone.utc).isoformat(),
        match_id=match_id or default_match_id(match),
        input_hash=sha256_file(input_path),
        table_hash=sha256_file(table_path),
        predicted_direction=predicted,
        actual_direction=actual,
        hit=hit,
        status=status,
        failure_bucket=bucket,
        failure_reasons=reasons,
        adverse_exclusions=adverse_exclusions,
        relative_non_selected=relative_non_selected,
        direction_statuses=_direction_statuses(result),
        final_selection_method=method,
        final_confidence=confidence,
        company_relation=company_relation,
        p1_distribution_type=p1_distribution,
        stop_reason=result.stop_reason,
        notes=list(result.notes),
    )


def append_oos_record(record: OOSRecord, ledger_path: str | Path) -> None:
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_oos_ledger(ledger_path: str | Path) -> list[OOSRecord]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    records: list[OOSRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(OOSRecord(**json.loads(line)))
    return records


def summarize_oos(records: Iterable[OOSRecord]) -> OOSSummary:
    rows = list(records)
    evaluated = [r for r in rows if r.hit is not None]
    hits = sum(1 for r in evaluated if r.hit is True)
    misses = sum(1 for r in evaluated if r.hit is False)
    by_bucket: dict[str, int] = {}
    for r in rows:
        if r.failure_bucket:
            by_bucket[r.failure_bucket] = by_bucket.get(r.failure_bucket, 0) + 1
    hit_rate = round(hits / len(evaluated), 4) if evaluated else None
    return OOSSummary(
        total=len(rows),
        evaluated=len(evaluated),
        hits=hits,
        misses=misses,
        hit_rate=hit_rate,
        by_failure_bucket=by_bucket,
    )


def render_oos_record(record: OOSRecord) -> str:
    lines = [
        "## OOS 赛后回填",
        f"- 比赛：{record.home_team} vs {record.away_team}",
        f"- 赛前结构方向：{record.predicted_direction or '未形成'}",
        f"- 实际方向：{record.actual_direction or '未提供'}",
        f"- 回填状态：{record.status}",
    ]
    if record.hit is not None:
        lines.append(f"- 是否命中：{'是' if record.hit else '否'}")
    if record.failure_bucket:
        lines.append(f"- 错因桶：{record.failure_bucket}")
    if record.adverse_exclusions:
        lines.append(f"- 赛前明确不利排除：{'、'.join(record.adverse_exclusions)}")
    if record.relative_non_selected:
        lines.append(f"- 赛前相对未选中：{'、'.join(record.relative_non_selected)}")
    if record.failure_reasons:
        lines.append("- 回填说明：")
        lines.extend([f"  * {reason}" for reason in record.failure_reasons])
    lines.append("- 边界：OOS 只记录和归因，不允许用单场结果自动升级规则。")
    return "\n".join(lines)
