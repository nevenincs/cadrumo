---
tags:
  - '#research'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:3e9853ac6591261495b3d83716ebb0d5e0c06be9de4ecf17a2898b3184ae0a76'
related:
  - "[[2026-06-30-cpdefix-calculation-allgreen-audit]]"
  - "[[2026-07-05-cpdefix-followup-allgreen-adr]]"
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# `cpdefix-followup-allgreen` research: `campaign disposition grounding`

This research grounds the follow-up campaign tracker after the shared worktree advanced beyond the June cpdefix closeout. The question is not a new product design; it is how to keep an open-ended calculation allgreen campaign honest when old persona and audit evidence may be stale, while still dispatching code fixers for live defects.

## Findings

### Current evidence must override stale blocker labels

RAG and source confirmation showed the older resolver-contract closeout still names M720 row carrier and M347 no-binding blockers that are no longer accurate as written. The current M720 plan and audit record the row-carrier implementation, `CalculationSourceResolution.row_binding_values`, foreign-assets resolver enrollment, and replay/export preservation. The focused M720 row-carrier gate passed with 62 tests.

Source locators:

- `src/aeat/application/aggregation/_source_mesh.py`: row-indexed binding carrier and merge ownership.
- `src/aeat/application/aggregation/_foreign_assets.py`: foreign-assets resolver returns `row_binding_values`.
- `src/aeat/application/modelo/_calculation_actions.py`: calculate path includes `ForeignAssetsAggregationSourceResolver`.
- `.vault/plan/2026-07-05-modelo-720-prior-year-baseline-plan.md`: W03 row-carrier and enrollment steps checked.
- `.vault/audit/2026-07-05-modelo-720-prior-year-baseline-audit.md`: close review finds no S16 blockers.

### M347 has current registry support, but not a counterpart-provider trigger

M347 no longer has zero relevant bindings. The current registry declares invoice-owned summary bindings and the registry test proves the M347 invoice-total declaration threshold. This does not promote the reserved counterpart provider because the bindings use invoice-owned source kinds, not `ledger_transaction` or `purchase_invoice_evidence`.

Source locators:

- `src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py`: proves M347 summary binding source and threshold behavior.
- `src/aeat/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/bindings/0001-counterpart-summary.toml`: M347 summary binding data.
- `src/aeat/application/aggregation/tests/test_per_modelo_service.py`: counterpart service tests assert the reserved resolver does not claim invoice-owned M347 bindings.
- `.vault/audit/2026-07-04-m347-invoice-source-summary-audit.md`: records the invoice-owned M347 summary route.

### The counterpart provider remains intentionally gated

The accepted counterpart-source provider ADR remains authoritative for `ledger_transaction` and `purchase_invoice_evidence`. It rejects generic provider shims and requires the repository-backed provider, source-kind promotion, registry declaration, and correctness gate to co-land. The current source-mesh disposition still keeps those two kinds reserved, and current M347 registry support does not declare them.

Source locators:

- `.vault/adr/2026-07-05-cpdefix-followup-allgreen-adr.md`: accepted provider design and promotion trigger.
- `src/aeat/application/aggregation/_source_mesh.py`: `RESERVED_SOURCE_KINDS` still contains `ledger_transaction` and `purchase_invoice_evidence`.
- `src/aeat/application/aggregation/_counterpart.py`: repository-free resolver remains a supplied-observation adapter.

### The campaign needs a tracker, not forced code churn

The open-ended persona campaign cannot assume testimonial evidence is bounded or current. A wave-based plan should first separate stale from live evidence, then brief code fixers only for current, reproducible product defects. The tracker must preserve the user's constraints: every code fixer runs `vaultspec-rag` before editing, no destructive git operations, no reexport or shim workaround unless the owning public source already exists, and completed agents are closed promptly.

Source locators:

- `.vault/audit/2026-06-30-cpdefix-calculation-allgreen-audit.md`: scoped June calculation checkpoint, not full-tree certification.
- `tmp/personas/_cpdefix-closeout-ledger.md`: persona artifact classifications and residual evidence gaps.
- `.vault/audit/2026-07-05-cpdefix-followup-allgreen-audit.md`: current stale-versus-live resync.
