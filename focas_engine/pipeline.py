from __future__ import annotations

from .adverse import select_final_direction
from .checks import (
    basic_context_gate,
    natural_pull_gate,
    odds_gate,
    odds_system_routing_gate,
    original_book_mode_gate,
    original_distribution_gate,
    strength_gate,
)
from .config import HARD_DATA_SOURCE, is_legacy_hard_data_source, resolve_table_path
from .context_modifiers import build_event_context_modifiers
from .expected_interval import audit_opening_interval, expected_interval_from_table
from .integrated_structure import integrated_structure_judgement
from .models import (
    CompanyOdds,
    MatchContext,
    NarrativeMaterial,
    NaturalPull,
    OriginalBookMode,
    PipelineResult,
    StrengthContext,
)
from .motives import motive_readings, odds_moves, opening_motive_readings
from .narrative_audit import build_narrative_audit
from .odds_coordinate import build_odds_coordinates
from .odds_system import build_odds_system_routes
from .original_distribution import build_original_distribution
from .original_modes import fill_original_book_mode
from .p1_core import build_p1_core
from .relative_selection import select_relative_mainline
from .scenario_audit import build_scenario_audit
from .solution_audit import (
    build_bookmaker_topic_usage_audit,
    build_final_structure_judgement,
    build_future_adjustment_plan,
    build_market_pull_audit,
    build_opening_board_audit,
    build_optimal_solution_audit,
    build_psychological_interval_audit,
)
from .stage9 import describe_odds_face, odds_face_and_company_motive_analysis
from .strength import fill_strength_context
from .strength import STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED

STRENGTH_SOURCE_AUTO_ESTIMATED_REVIEW_REQUIRED = "AUTO_ESTIMATED_REVIEW_REQUIRED"


class FocasPipeline:
    def __init__(self, *, table_path: str | None = None):
        self.table_path = str(resolve_table_path(table_path))

    @staticmethod
    def _stop(
        result: PipelineResult,
        reason: str,
        *,
        stop_node: str | None = None,
        missing_fields: list[str] | None = None,
    ) -> PipelineResult:
        result.stop = True
        result.stop_reason = reason
        result.report_mode = "STOP_REPORT_ONLY"
        result.stop_node = stop_node
        if missing_fields:
            result.missing_fields.extend(item for item in missing_fields if item not in result.missing_fields)
        result.odds_analysis_status = "FORBIDDEN"
        result.mainline_output_status = "FORBIDDEN"
        return result

    def run(
        self,
        *,
        match: MatchContext,
        strength: StrengthContext,
        pulls: list[NaturalPull],
        narrative_materials: list[NarrativeMaterial] | None = None,
        book_mode: OriginalBookMode,
        odds: list[CompanyOdds],
    ) -> PipelineResult:
        result = PipelineResult(gates=[])
        result.hard_data_source = HARD_DATA_SOURCE

        basic_gate = basic_context_gate(match)
        result.gates.append(basic_gate)
        if not basic_gate.ok:
            result.basic_context_status = "INCOMPLETE"
            return self._stop(
                result,
                f"Basic_Context_Status = INCOMPLETE｜{basic_gate.stop_message()}",
                stop_node="基本面硬闸门",
                missing_fields=basic_gate.missing,
            )
        result.basic_context_status = "COMPLETE"
        result.context_modifiers = build_event_context_modifiers(match)

        strength, estimate = fill_strength_context(strength, match)
        result.strength_context = strength
        result.strength_estimate = estimate
        result.strength_source = getattr(estimate, "source", STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED)
        strength_result = strength_gate(strength)
        result.gates.append(strength_result)
        if not strength_result.ok:
            return self._stop(
                result,
                strength_result.stop_message(),
                stop_node="广义实力分档闸门",
                missing_fields=strength_result.missing,
            )
        if result.strength_source == STRENGTH_SOURCE_MANUAL_REVIEW_REQUIRED:
            result.strength_source = STRENGTH_SOURCE_AUTO_ESTIMATED_REVIEW_REQUIRED
            source_reason = getattr(estimate, "source_reason", "")
            if source_reason:
                result.notes.append(source_reason)
            result.notes.append(
                "Strength source requires review, but filled broad-strength fields passed strength_gate; continuing into skeleton and optimal-solution audits."
            )
        result.expected_opening_interval = expected_interval_from_table(strength=strength, estimate=estimate)

        pull_gate = natural_pull_gate(pulls)
        result.gates.append(pull_gate)
        if not pull_gate.ok:
            return self._stop(result, pull_gate.stop_message(), stop_node="三项自然拉力闸门", missing_fields=pull_gate.missing)

        # Stage 5: build pre-odds distribution. This function intentionally has no odds input.
        result.original_distribution = build_original_distribution(
            match=match,
            strength=strength,
            pulls=pulls,
        )
        distribution_gate = original_distribution_gate(result.original_distribution)
        result.gates.append(distribution_gate)
        if not distribution_gate.ok:
            return self._stop(result, distribution_gate.stop_message(), stop_node="原始分布闸门", missing_fields=distribution_gate.missing)

        book_mode, mode_estimate = fill_original_book_mode(
            book_mode,
            match=match,
            strength=strength,
            pulls=pulls,
            original_distribution=result.original_distribution,
        )
        result.book_mode_context = book_mode
        result.original_mode_estimate = mode_estimate
        mode_gate = original_book_mode_gate(book_mode)
        result.gates.append(mode_gate)
        if not mode_gate.ok:
            return self._stop(result, mode_gate.stop_message(), stop_node="原书模式挂接闸门", missing_fields=mode_gate.missing)

        input_odds_gate = odds_gate(odds)
        result.gates.append(input_odds_gate)
        if not input_odds_gate.ok:
            return self._stop(result, input_odds_gate.stop_message(), stop_node="赔率输入闸门", missing_fields=input_odds_gate.missing)

        result.p1_core = build_p1_core(
            match=match,
            strength=strength,
            pulls=pulls,
            book_mode=book_mode,
            original_distribution=result.original_distribution,
        )

        # Stage 7: identify each snapshot's return-rate system before lookup.
        # Published odds remain unchanged; the system selects the xlsx sheet.
        result.odds_system_conversions = build_odds_system_routes(odds)
        routing_gate = odds_system_routing_gate(result.odds_system_conversions)
        result.gates.append(routing_gate)
        if not routing_gate.ok:
            return self._stop(
                result,
                f"TABLE_LOOKUP_FORBIDDEN｜{routing_gate.stop_message()}",
                stop_node="赔率体系识别与骨架表路由闸门",
                missing_fields=routing_gate.missing,
            )

        # Stage 8: route unchanged institution odds into each detected system sheet.
        if is_legacy_hard_data_source(self.table_path):
            return self._stop(
                result,
                f"TABLE_READ_CONFIRMED = NO｜旧版数据源不得用于正式查表：{self.table_path}",
                stop_node="现代骨架数据源闸门",
            )
        try:
            result.odds_coordinates = build_odds_coordinates(
                xlsx_path=self.table_path,
                league=match.league_for_table or "",
                conversions=result.odds_system_conversions,
            )
        except Exception as exc:
            return self._stop(
                result,
                f"TABLE_READ_CONFIRMED = NO｜现代骨架数据源读取失败：{exc}",
                stop_node="现代骨架查表闸门",
            )
        all_low_results = result.odds_coordinates.current_low_table_results(match.league_for_table or "")
        hard_companies = {"威廉", "立博", "William", "Ladbrokes"}
        result.table_results = [item for item in all_low_results if item.company in hard_companies]
        result.notes.extend(result.odds_coordinates.notes)
        non_home_low = [
            coordinate
            for coordinate in result.odds_coordinates.coordinates
            if coordinate.direction != "主胜"
        ]
        result.skeleton_scope_status = (
            "HOME_AXIS_PRECISE"
            if not non_home_low
            else "HOME_AXIS_ONLY_REVIEW_REQUIRED"
        )
        if non_home_low:
            result.notes.append(
                "SKELETON_SCOPE = HOME_AXIS_ONLY_REVIEW_REQUIRED: "
                "draw/away low cases remain combination references and cannot be treated as precise directional skeletons."
            )

        result.interval_audit = audit_opening_interval(
            strength=strength,
            estimate=result.strength_estimate,
            odds_coordinates=result.odds_coordinates,
            expected=result.expected_opening_interval,
            xlsx_path=self.table_path,
        )
        result.expected_interval_status = (
            "CONFIRMED"
            if result.interval_audit.ok
            and all(item.hard_status == "CONFIRMED" for item in result.interval_audit.audits)
            else "REVIEW_REQUIRED"
        )
        result.notes.extend(result.interval_audit.notes)

        allowed_lookup_status = {"TABLE_READ_CONFIRMED"}
        if len(result.table_results) < 2 or not all(
            item.lookup_status in allowed_lookup_status for item in result.table_results
        ):
            return self._stop(
                result,
                "TABLE_READ_CONFIRMED = NO｜William / Ladbrokes 未全部按各自返还率体系使用原始赔率完成现代骨架查表；"
                "Mainline_Output = FORBIDDEN。Avg 只能作为市场背景。",
                stop_node="现代骨架查表闸门",
            )
        result.table_read_confirmed = "YES"
        result.odds_analysis_status = "ALLOWED"

        # Stage 9: disassemble actions, face shape and company purpose.
        result.odds_moves = odds_moves(odds, conversions=result.odds_system_conversions)
        odds_face = describe_odds_face(result.odds_moves)
        opening_readings = opening_motive_readings(
            interval_audit=result.interval_audit,
            original_distribution=result.original_distribution,
            pulls=pulls,
            context_summary=result.context_modifiers.summary() if result.context_modifiers else "",
        )
        result.motive_readings = motive_readings(
            moves=result.odds_moves,
            pulls=pulls,
            table_results=result.table_results,
            p1_core=result.p1_core,
            original_distribution=result.original_distribution,
            strength_gap=strength.final_gap,
            expected_interval=result.interval_audit.expected,
            odds_face=odds_face,
            context_summary=result.context_modifiers.summary() if result.context_modifiers else "",
        )
        result.stage_9_analysis = odds_face_and_company_motive_analysis(
            moves=result.odds_moves,
            motive_readings=result.motive_readings,
            p1_core=result.p1_core,
            odds_coordinates=result.odds_coordinates,
            opening_readings=opening_readings,
        )
        result.company_semantics = result.stage_9_analysis.company_relation
        result.narrative_audit = build_narrative_audit(
            pulls=pulls,
            materials=narrative_materials,
            opening_readings=result.stage_9_analysis.opening_motive_chain,
            motive_readings=result.motive_readings,
        )
        result.psychological_interval_audit = build_psychological_interval_audit(
            expected=result.interval_audit.expected,
            odds_coordinates=result.odds_coordinates,
            xlsx_path=self.table_path,
        )
        result.opening_board_audit = build_opening_board_audit(
            expected=result.interval_audit.expected,
            odds_coordinates=result.odds_coordinates,
            xlsx_path=self.table_path,
        )
        result.market_pull_audit = build_market_pull_audit(
            pulls=pulls,
            original_distribution=result.original_distribution,
            narrative_audit=result.narrative_audit,
        )
        result.bookmaker_topic_usage_audit = build_bookmaker_topic_usage_audit(
            market_pull_audit=result.market_pull_audit,
            narrative_audit=result.narrative_audit,
            opening_board_audit=result.opening_board_audit,
        )
        result.optimal_solution_audit = build_optimal_solution_audit(
            expected=result.interval_audit.expected,
            market_pull_audit=result.market_pull_audit,
            opening_board_audit=result.opening_board_audit,
            bookmaker_topic_usage_audit=result.bookmaker_topic_usage_audit,
        )
        result.future_adjustment_plan = build_future_adjustment_plan(
            optimal_solution_audit=result.optimal_solution_audit,
            opening_board_audit=result.opening_board_audit,
        )
        result.final_structure_judgement = build_final_structure_judgement(
            optimal_solution_audit=result.optimal_solution_audit,
        )

        # Stage 10: synthesize the full reasoning chain. Summary statuses are last, not first.
        result.integrated_structure = integrated_structure_judgement(
            strength=strength,
            pulls=pulls,
            original_distribution=result.original_distribution,
            book_mode=book_mode,
            odds_coordinates=result.odds_coordinates,
            interval_audit=result.interval_audit,
            stage_9=result.stage_9_analysis,
        )
        result.direction_judgements = result.integrated_structure.summary_status
        result.final_direction, note = select_final_direction(result.direction_judgements)
        result.notes.append(note)

        adverse_count = len(result.integrated_structure.adverse_excluded_directions)
        if result.final_direction is None and adverse_count <= 1:
            relative = select_relative_mainline(
                judgements=result.direction_judgements,
                strength=strength,
                pulls=pulls,
                book_mode=book_mode,
                table_results=result.table_results,
                motive_readings=result.motive_readings,
                match=match,
                p1_core=result.p1_core,
                company_semantics=result.company_semantics,
                interval_audit=result.interval_audit,
                original_distribution=result.original_distribution,
                opening_motive_readings=result.stage_9_analysis.opening_motive_chain,
            )
            result.relative_selection = relative
            result.structural_lean = relative.selected_direction or None
            result.integrated_structure.relative_weaker_directions = list(relative.relative_non_selected)
            result.notes.append(
                f"第二阶段相对主线选择：{relative.selected_direction}｜置信度={relative.confidence}。"
                "相对弱不等于不利排除。"
            )

        decision_warnings: list[str] = []
        if result.final_direction is None:
            if result.structural_lean:
                decision_warnings.append("no complete two-adverse directional chain; using relative structural lean")
            else:
                decision_warnings.append("no complete directional evidence chain")
        if result.expected_interval_status != "CONFIRMED":
            decision_warnings.append("theoretical skeleton interval requires review")
        if result.skeleton_scope_status != "HOME_AXIS_PRECISE":
            decision_warnings.append("skeleton workbook is home-axis precise only for this odds shape")
        if result.narrative_audit.review_required:
            decision_warnings.append("source-level three-direction narrative audit is incomplete")

        if result.final_direction:
            result.decision_status = "EXECUTE" if not decision_warnings else "LEAN"
            result.mainline_output_status = "ALLOWED" if not decision_warnings else "ALLOWED_WITH_CAUTION"
        elif result.structural_lean:
            result.final_direction = result.structural_lean
            result.decision_status = "LEAN"
            result.mainline_output_status = "ALLOWED_WITH_CAUTION"
            result.notes.append(
                "Structural LEAN: relative mainline selected; final PASS gate is disabled for analysis mode."
            )
        else:
            result.final_direction = "PASS"
            result.decision_status = "PASS"
            result.mainline_output_status = "PASS"
            result.notes.append("No selectable structural lean was produced.")
        if decision_warnings:
            result.notes.append("Decision warnings: " + "; ".join(decision_warnings))
        if result.final_structure_judgement:
            judgement = result.final_structure_judgement
            result.notes.append(
                f"Optimal solution layer: {judgement.status}"
                + (f"｜direction={judgement.direction}" if judgement.direction else "")
                + f"｜reason={judgement.reason}"
            )
            if judgement.status == "EXECUTE" and judgement.direction:
                result.final_direction = judgement.direction
                result.decision_status = "EXECUTE"
                result.mainline_output_status = "ALLOWED"
            elif judgement.status == "BETTER_SOLUTION_ONLY" and judgement.direction:
                result.final_direction = judgement.direction
                result.decision_status = "BETTER_SOLUTION_ONLY"
                result.mainline_output_status = "ALLOWED_WITH_CAUTION"
            elif judgement.status in {"NO_OPTIMAL_SOLUTION", "NO_BET_STRUCTURE"}:
                result.final_direction = "NO_BET"
                result.decision_status = judgement.status
                result.mainline_output_status = "NO_BET_STRUCTURE"
        result.report_mode = "FULL_REPORT"
        result.scenario_audit = build_scenario_audit(result=result)
        return result
