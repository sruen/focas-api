# FOCAS API v1.1.6-material Change Log

## Purpose

This version changes the API from a final-direction engine into a material-audit and conflict-check tool. V3.9.1 and V4 project-source documents remain the judgement layer. GPT must independently apply the analysis logic before final output.

## Main changes

1. Added `FOCASGPT_CORE_INSTRUCTIONS_v1.0.md`.
2. Added `project_sources/`:
   - `V3.9.1_欧赔核心分析完整体系_升级完整版.txt`
   - `V4.0_足球体彩欧赔分析体系_完整版.txt`
3. Replaced API contract with material-audit mode:
   - `analysis_mode = MATERIAL_AUDIT_ONLY`
   - `lean_output_allowed = false`
   - `backend_final_is_reference_only = true`
   - `gpt_independent_judgement_required = true`
4. Added `/v1/audit` with operationId `auditFocasMaterials`.
5. Added `/v1/verify` with operationId `verifyIndependentJudgement`.
6. Kept `/v1/analyze` as a compatibility alias, but it now returns material audit only.
7. Removed `final_structure_judgement` from primary payload.
8. Added `backend_reference_judgement` with direction fields scrubbed.
9. Scrubbed selected direction from `scenario_simulation_reference`.
10. Updated OpenAPI schema to v1.1.6-material and validated YAML parsing.

## Intended runtime chain

GPT searches and structures pre-match fundamentals → API audits materials → GPT applies V3.9.1/V4 independent reasoning → API verifies conflicts → GPT outputs final bookmaker mainline and structure grade.
