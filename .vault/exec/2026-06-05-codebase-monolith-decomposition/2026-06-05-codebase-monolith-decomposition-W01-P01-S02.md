---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S02'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W01.P01.S02 - callable complexity proxy inventory

Scope: `src/aeat`.

## Description

- Ran AST discovery for functions over 180 lines or with more than 35 branch-node hits.
- Used line count plus branch-node count as a proxy inventory for later decomposition and guard work.
- Ran semantic discovery with `vaultspec-rag` against code for monolith and guard surfaces.

## Outcome

Top callable hotspots from the proxy inventory:

```text
 273 lines  11 branches src/aeat/application/modelo/_actions.py:3264 amend_modelo_revision
 270 lines  19 branches src/aeat/domain/iva_compensation/_reconciliation.py:180 reconcile_iva_compensation_wallet
 257 lines  17 branches src/aeat/tests/fixtures/justificantes/_generate.py:2833 main
 243 lines  23 branches src/aeat/entrypoints/cli/_modelo_projection_cli.py:40 register_projection_commands
 241 lines  15 branches src/aeat/application/modelo/_actions.py:2421 verify_modelo_revision
 235 lines  14 branches src/aeat/application/modelo/_actions.py:3539 import_external_filing_evidence
 230 lines   4 branches src/aeat/tests/fixtures/justificantes/_generate.py:2003 _draw_modelo_303_corpus
 222 lines  14 branches src/aeat/adapters/outbound/google/_calc_sheets_apply.py:1067 apply_export_plan
 221 lines  10 branches src/aeat/application/ledger/_actions.py:1747 merge_transactions
 206 lines   8 branches src/aeat/entrypoints/cli/_ledger_evidence_cli.py:35 register_evidence_commands
 199 lines   7 branches src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py:23 register_iva_wallet_commands
 196 lines   1 branches src/aeat/domain/calculations/registry/_validate_revision_sections.py:59 validate_revision_definition
 194 lines  18 branches src/aeat/entrypoints/cli/_ledger.py:540 ledger_classify
 193 lines   4 branches src/aeat/entrypoints/cli/tests/test_modelo_projection.py:276 test_modelo_project_m130_to_m100_full_year_aggregation
 192 lines   0 branches src/aeat/adapters/outbound/aeat/export/_formats/tests/test_fichero_boe_roundtrip.py:631 test_modelo_303_golden_sha_fichero_boe
 191 lines  18 branches src/aeat/entrypoints/cli/_config/_profile_censo.py:99 register
 188 lines  25 branches src/aeat/core/observability/_context.py:148 run_context
 184 lines  21 branches src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:949 _fresh_login_locked
```

Semantic discovery completed through the running RAG service and surfaced existing CLI architecture and module-size guard tests, including `test_architecture_boundaries.py` and `test_cli_module_size.py`.

## Notes

The first Python inventory attempt used an invalid POSIX heredoc form in PowerShell. It was rerun with a PowerShell here-string into Python stdin.
