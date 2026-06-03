from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .io import load_input_with_report
from .pipeline import FocasPipeline
from .report import render_frontend_report
from .oos import build_oos_record, append_oos_record, render_oos_record, load_oos_ledger, summarize_oos
from .config import HARD_DATA_SOURCE


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FOCAS v1.7 executable pipeline.")
    parser.add_argument("input_json", help="Match input JSON path or FOCAS match package .zip path")
    parser.add_argument("--export-normalized-json", help="把自动读取后的标准输入 JSON 导出到指定路径")
    parser.add_argument("--show-loader-report", action="store_true", help="显示比赛包自动读取诊断信息")
    parser.add_argument("--table", default=HARD_DATA_SOURCE, help="FOCAS corrected modern skeleton xlsx path")
    parser.add_argument("--json", action="store_true", help="Print raw JSON result")
    parser.add_argument("--debug", action="store_true", help="Print engineering/debug output instead of frontend report")
    parser.add_argument("--backend-audit", action="store_true", help="在默认前台报告后附加后台技术审计字段")
    parser.add_argument("--actual-direction", help="赛后实际方向：主胜 / 平局 / 客胜，也支持 H/D/A")
    parser.add_argument("--score", help="赛后比分，例如 2-1 或 1:1；未提供 actual-direction 时自动转方向")
    parser.add_argument("--oos-ledger", help="把 OOS 回填记录追加到指定 JSONL 文件")
    parser.add_argument("--oos-summary", action="store_true", help="读取 --oos-ledger 并输出 OOS 汇总")
    args = parser.parse_args()

    if args.oos_summary:
        if not args.oos_ledger:
            raise SystemExit("--oos-summary requires --oos-ledger")
        summary = summarize_oos(load_oos_ledger(args.oos_ledger))
        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
        return

    loaded = load_input_with_report(args.input_json)
    match, strength, pulls, book_mode, odds = loaded.as_tuple()

    if args.export_normalized_json:
        from pathlib import Path
        Path(args.export_normalized_json).write_text(json.dumps(loaded.raw, ensure_ascii=False, indent=2), encoding="utf-8")
    result = FocasPipeline(table_path=args.table).run(
        match=match,
        strength=strength,
        pulls=pulls,
        narrative_materials=loaded.narrative_materials,
        book_mode=book_mode,
        odds=odds,
    )

    oos_record = None
    if args.actual_direction or args.score:
        oos_record = build_oos_record(
            match=match,
            result=result,
            actual_direction=args.actual_direction,
            score=args.score,
            input_path=args.input_json,
            table_path=args.table,
        )
        if args.oos_ledger:
            append_oos_record(oos_record, args.oos_ledger)

    if args.json:
        payload = {"pipeline": asdict(result)}
        if loaded.diagnostics:
            payload["loader"] = {"diagnostics": [asdict(d) for d in loaded.diagnostics], "source_files": loaded.source_files}
        if oos_record:
            payload["oos"] = asdict(oos_record)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    loader_text = ""
    if args.show_loader_report and loaded.diagnostics:
        loader_text = "【自动读取诊断】\n" + "\n".join(f"- {d.level}｜{d.message}" + (f"｜{d.file}" if d.file else "") for d in loaded.diagnostics) + "\n\n"

    if not args.debug:
        text = loader_text + render_frontend_report(
            match=match,
            strength=strength,
            pulls=pulls,
            book_mode=book_mode,
            odds=odds,
            result=result,
            backend_audit=args.backend_audit,
        )
        if oos_record:
            text += "\n\n" + render_oos_record(oos_record)
        print(text)
        return

    if loader_text:
        print(loader_text, end="")
    print("FOCAS v1.7 运行结果")
    print("=" * 40)
    for gate in result.gates:
        print(gate.stop_message())

    # Print executable estimates even when a later gate stops the run.
    # This makes the engine useful as a debugger: it shows where the pipeline got to,
    # instead of hiding already completed modules behind the final STOP.
    if result.strength_estimate:
        e = result.strength_estimate
        print("\n广义实力辅助分档")
        print(f"- 主队：{e.home.team}｜{e.home.grade}｜score={e.home.score}｜近况PPG={e.home.recent_points_per_game}")
        print(f"- 客队：{e.away.team}｜{e.away.grade}｜score={e.away.score}｜近况PPG={e.away.recent_points_per_game}")
        print(f"- 最终档位差：{e.final_gap_label}｜置信度：{e.confidence}")
        print(
            f"- 理论心理区间：{e.theoretical_psychological_interval}"
            f"｜主赔={e.theoretical_home_odds_range}"
            f"｜平赔={e.theoretical_draw_odds_reference}"
            f"｜客赔={e.theoretical_away_odds_reference}"
        )
        for warning in e.warnings:
            print(f"  * {warning}")

    if result.original_distribution:
        d = result.original_distribution
        print("\n赔率读取前原始分布")
        print(f"- 类型：{d.distribution_type}")
        print(f"- 主胜 / 平局 / 客胜压力：{d.home_pressure} / {d.draw_pressure} / {d.away_pressure}")
        print(f"- 市场第一眼方向：{d.first_eye_direction or '未确认'}")

    if result.original_mode_estimate:
        e = result.original_mode_estimate
        print("\n原书模式自动挂接")
        print(f"- 主模式：{e.primary_mode}")
        print(f"- 挂接原因：{e.primary_reason}")
        print(f"- 重点观察：{e.key_odds_to_watch}")
        print(f"- 易误读：{e.easiest_misread}")
        print("- 备选模式：")
        for c in e.options[:5]:
            print(f"  * {c.mode}｜score={c.score}｜{c.reason}")
        for warning in e.warnings:
            print(f"  * {warning}")

    if result.p1_core:
        p1 = result.p1_core
        print("\nP1底层逻辑")
        print(f"- 原始分布类型：{p1.distribution_type}")
        print(f"- 大众第一眼方向：{p1.first_eye_direction or '未确认'}")
        print(f"- 最易分散方向：{p1.easiest_to_disperse_direction or '未确认'}")
        print("- 方向画像：")
        for prof in p1.profiles:
            print(
                f"  * {prof.direction}｜原始分布={prof.original_distribution_strength}"
                f"｜信心承载={prof.confidence_carrying}"
                f"｜分散支持={prof.dispersion_support}"
                f"｜预期开法={prof.expected_board_style}"
                f"｜角色={prof.distribution_role}"
            )
        print("- 误读拦截：")
        for block in p1.misread_blocks[:5]:
            print(f"  * {block.pattern}｜{block.blocked_reason}")

    if result.stop:
        print("\nSTOP:", result.stop_reason)
        if not result.table_results and not result.odds_coordinates:
            return

    if result.odds_system_conversions:
        print("\n返还率体系识别与骨架表路由")
        for c in result.odds_system_conversions:
            print(
                f"- {c.company}｜{c.snapshot_type}｜raw={c.raw_home}/{c.raw_draw}/{c.raw_away}"
                f"｜返还率={c.raw_payout_percent}%｜{c.detected_system}"
                f"｜table_route={c.target_system}｜赔率数值不转换｜status={c.conversion_status}"
            )

    if result.odds_coordinates:
        print("\nStage 8 现代骨架坐标归位")
        for company_set in result.odds_coordinates.company_sets:
            changed = "｜跨体系" if company_set.system_changed else ""
            print(
                f"- {company_set.company}｜初赔{company_set.initial_system}({company_set.initial_return_rate}%)"
                f" → 当前{company_set.current_system}({company_set.current_return_rate}%){changed}"
            )
            for c in company_set.coordinates:
                low_flag = "低赔项" if c.is_snapshot_low else "非低赔参考"
                print(
                    f"  * {c.time_point} {c.direction} {c.odds_value}｜{low_flag}"
                    f"｜{c.table_direction}｜区间{c.interval_id}｜{c.water_band}"
                    f"｜{c.deviation}｜{c.lookup_status}｜{c.evidence_level}｜row={c.row_number}"
                )
                for warning in c.warnings[:2]:
                    print(f"    - {warning}")
        for note in result.odds_coordinates.notes:
            print(f"  * {note}")
    else:
        print("\n现代骨架区间查表")
        for t in result.table_results:
            print(f"- {t.company}｜{t.system}｜{t.direction}｜区间{t.interval_id}｜{t.water_band}｜现实低赔 {t.actual_low_odds}｜{t.deviation}｜row={t.row_number}")

    if result.interval_audit:
        print("\n初赔合理性审计：理论骨架 vs 机构实际初赔")
        print("- 必须先按机构初赔返还率识别体系，再从该体系 sheet 读取 P4 理论区间赔率。")
        for audit in result.interval_audit.audits:
            print(
                f"- {audit.company}｜体系={audit.system or '未确认'}｜理论区间={audit.expected_interval_id}"
                f"｜理论主赔范围={audit.expected_home_min}-{audit.expected_home_max}"
                f"｜平赔参考={audit.expected_draw_reference_min}-{audit.expected_draw_reference_max}"
                f"｜负赔参考={audit.expected_away_reference_min}-{audit.expected_away_reference_max}"
                f"｜机构原始初赔={audit.raw_opening_home}/{audit.raw_opening_draw}/{audit.raw_opening_away}"
                f"｜主/平/负偏差={audit.home_range_deviation}/{audit.draw_reference_deviation}/{audit.away_reference_deviation}"
                f"｜主赔合理性={audit.price_reasonableness}｜审计状态={audit.hard_status}"
            )

    if result.stop:
        return

    print("\nStage 9 赔率动作 + 赔面 + 公司目的拆解")
    for r in result.motive_readings:
        print(f"- {r.company} {r.direction} {r.action}｜{r.motive_type}｜{r.bookmaker_meaning}")


    if result.company_semantics:
        cs = result.company_semantics
        print("\nStage 9 公司关系")
        print(f"- 公司关系：{cs.relation_type}")
        print(f"- 双公司主线承接确认：{', '.join(cs.confirmed_directions) if cs.confirmed_directions else '无'}")
        print(f"- 双公司风险修正：{', '.join(getattr(cs, 'risk_repair_directions', [])) if getattr(cs, 'risk_repair_directions', []) else '无'}")
        print(f"- 双公司分流/过渡：{', '.join(getattr(cs, 'dispersion_directions', [])) if getattr(cs, 'dispersion_directions', []) else '无'}")
        print(f"- 确认不足：{', '.join(cs.unconfirmed_directions) if cs.unconfirmed_directions else '无'}")
        print(f"- 冲突方向：{', '.join(cs.conflict_directions) if cs.conflict_directions else '无'}")
        print(f"- 双公司不利压力证据：{', '.join(cs.adverse_pressure_directions) if cs.adverse_pressure_directions else '无'}")
        for reading in cs.readings:
            print(
                f"  * {reading.company}｜关注={reading.primary_focus}"
                f"｜角色={reading.semantic_role}"
                f"｜确认={reading.confirmation_level}"
            )
            mainline_dirs = getattr(reading, 'mainline_confirmed_directions', reading.supported_directions)
            if mainline_dirs:
                print(f"    - 主线承接备选：{', '.join(mainline_dirs)}")
            if getattr(reading, 'risk_repair_directions', []):
                print(f"    - 风险修正备选：{', '.join(reading.risk_repair_directions)}")
            if reading.dispersed_directions:
                print(f"    - 分流/过渡备选：{', '.join(reading.dispersed_directions)}")
            if reading.adverse_pressure_directions:
                print(f"    - 不利压力证据：{', '.join(reading.adverse_pressure_directions)}")
            print(f"    - {reading.p1_connection}")
            print(f"    - {reading.coordinate_connection}")
            for ev in reading.evidence[:3]:
                print(f"    - {ev}")
            for warning in reading.warnings[:2]:
                print(f"    - {warning}")
        for note in cs.notes:
            print(f"  * {note}")

    if result.integrated_structure:
        print("\nStage 10 综合结构判断")
        print(f"- 主胜：{result.integrated_structure.home_integrated_judgement}")
        print(f"- 平局：{result.integrated_structure.draw_integrated_judgement}")
        print(f"- 客胜：{result.integrated_structure.away_integrated_judgement}")
        print(f"- 明确不利排除：{', '.join(result.integrated_structure.adverse_excluded_directions) if result.integrated_structure.adverse_excluded_directions else '无'}")
        print(f"- 只是未确认：{', '.join(result.integrated_structure.unconfirmed_directions) if result.integrated_structure.unconfirmed_directions else '无'}")

    print("\nStage 10 状态摘要")
    for j in result.direction_judgements:
        print(f"- {j.direction}: {j.status}｜{'；'.join(j.reasons)}")

    if result.relative_selection:
        r = result.relative_selection
        print("\n第二阶段相对主线选择")
        print(f"- 选择方向：{r.selected_direction}｜置信度：{r.confidence}")
        print(f"- 明确不利排除：{', '.join(r.adverse_exclusions) if r.adverse_exclusions else '无'}")
        print(f"- 相对未选中：{', '.join(r.relative_non_selected) if r.relative_non_selected else '无'}")
        for score in sorted(r.scores, key=lambda x: x.score, reverse=True):
            label = "SELECTED" if score.selected else "ADVERSE" if score.excluded_by_adverse else "RELATIVE"
            print(f"  * {score.direction}: {score.score}｜{label}")
            for reason in score.reasons[:5]:
                print(f"    - {reason}")
        for note in r.notes:
            print(f"  * {note}")

    print("\n结构输出")
    print(result.final_direction or result.notes[-1])

    if oos_record:
        print("\n" + render_oos_record(oos_record))


if __name__ == "__main__":
    main()
