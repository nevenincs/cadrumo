---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S147
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W04.P13-P17 — _modelo.py full migration + conformance gate

## Outcome

Migrated all 24 bare `_emit(ctx,` call sites in `_modelo.py` to the typed
`_emit_envelope` shape (minus the out-of-scope `_render_reconciliation_report`
helper which serves `reconcile` verbs not listed in the W04 burndown plan).

All 26 `OutputSchema` subclasses were authored in `_modelo_payloads.py` with
`@register_schema` decorators across P13–P16. All 26 new command paths were
added to `MIGRATED_COMMANDS` in `test_json_schema_conformance.py` as P17.

## Files changed

- `src/aeat/entrypoints/cli/_modelo.py` — 8 bare emit sites migrated in this
  session (modelo.readiness, modelo.aggregate, modelo.work.resume,
  modelo.history, modelo.project, modelo.iva_wallet.balance,
  modelo.iva_wallet.seed); prior sessions covered the remaining 16
- `src/aeat/entrypoints/cli/_modelo_payloads.py` — 26 OutputSchema subclasses
  authored across P13–P16 (prior sessions); no changes in this final session
- `src/aeat/entrypoints/cli/test_json_schema_conformance.py` — 26 new W04
  command paths added to MIGRATED_COMMANDS

## Gate

81 conformance tests pass (55 pre-W04 + 26 new W04 entries). Sequential run
confirms no regressions.

## W04 summary

- 24 bare `_emit(ctx,` call sites migrated (23 function verbs + the formulas verb)
- 26 `OutputSchema` subclasses authored with `@register_schema` decorators
- 26 `MIGRATED_COMMANDS` entries added
- Command paths covered: modelo.audit.{show,check,export,replay},
  modelo.work.{history,runs,resume}, modelo.filing_record.{list,show,import},
  modelo.verification_report.{list,show}, modelo.{list,describe,casillas},
  modelo.bindings.{list,preview}, modelo.formulas, modelo.{export,compare,history,
  project,readiness,aggregate}, modelo.iva_wallet.{balance,seed}
- Out of scope: _render_reconciliation_report helper (reconcile verbs not in W04)
- Commit: edd5835cb
