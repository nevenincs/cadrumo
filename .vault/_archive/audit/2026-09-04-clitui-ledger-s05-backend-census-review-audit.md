---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:29faf4485c94a54ae69d2a12c839d068d1cdbce4d3eb11ec18beec8f162cdc3e'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P02-S05]]"
---

# `clitui-ledger` audit: `S05 backend census review`

## Scope

Independent mandatory review of approved-plan step `W01.P02.S05`. The review
covered the backend census and source-set digest in
`2026-09-04-clitui-ledger-reference`, the S05 execution record, plan state and
feature index, and the public frontend-neutral behavior in the 21 cited modules
under `src/cadrumo/application/ledger/`. It did not review or change later
product implementation.

The review independently enumerated the admitted callables and their
annotations, searched the full Ledger package for competing application
operations, compared source consumers with the S04 CLI operation inventory,
and inspected the production workbench composition. It reproduced 58 admitted
public functions plus five public `PurchaseInvoiceEvidenceService` methods in
17 families, a family-count sum of 63, and source-set digest
`sha256:4b0d917dd20d155f348958559037695cb5bab356867a1c88305bb42080f3b2f0`.
The grouped request/result descriptions agree with the live callable
annotations. Repository factories, storage record readers, identity helpers,
payload serializers, and lower-level projectors are properly folded into their
owning operator products; after that fold, `ledger.workspace.read` is the sole
distinct backend-only product absent from the S04 CLI census. Its production
consumer is the installed workbench reader in `application/workbench_generation.py`.

The ten retained missing product/provenance families remain enumerated, G0 is
explicitly OPEN, and the S05 source commits changed only Vault documents. No
TUI or product implementation was introduced. The recorded focused command
was reproduced as 50 passing tests in 87.62 seconds. A read-only feature Vault
check passed all hard checks and reported only this audit's pre-attestation
template/index warnings.

## Findings

### s05-backend-census-review | high | Direct-proof census silently overstates backend evidence

The published 56-proved/seven-unproved assertion is not reproducible under its
stated "direct symbol-level behavioral test" criterion. An AST census of direct
calls across `src/cadrumo/application/ledger/tests/` found 50 of the 58 admitted
functions directly called. All five admitted evidence-service methods are also
directly exercised, producing 55 proved and eight unproved operations. The
published seven are indeed uncalled, but `build_llm_diagnostics_report` is an
omitted eighth gap. Exact repository-wide search found no test that directly
calls that public symbol: application tests call its private `_aggregate_usage`
helper, while CLI integration tests reach the report builder only through the
command adapter. That cannot satisfy a direct symbol-level backend proof when
the same census expressly rejects CLI-only proof for other operations.

This is HIGH because direct-proof enumeration is the primary S05 deliverable,
the reference presents the tally and exact gap set as authoritative evidence,
and the checked plan row plus execution record currently certify a false
completion fact. It also violates the no-silent-under-declaration requirement:
an unproved operation is collapsed into the proved total. No detector presently
fails when this proof attribution drifts; the green focused suite therefore
does not validate the census assertion.

### remediation-retest | low | RESOLVED: exact direct-proof tally and gap set are corrected

Commit `6a33383783` corrects the authoritative reference to 55 directly proved
operations and eight unproved operations, explicitly including
`ledger.llm.diagnostics` and `build_llm_diagnostics_report`. It also corrects
the S05 execution receipt to eight direct-proof gaps and restores the S05 plan
checkbox only after those facts agree. Independent AST retest reproduced 50
directly called public functions plus all five service methods and the exact
eight-name absence set. The original HIGH is resolved. The later S13 reopening
detector remains correctly open and is not silently claimed by S05.

The unchanged denominator also re-reproduces as 63 operations in 17 families,
58 functions plus five service methods, with source digest
`sha256:4b0d917dd20d155f348958559037695cb5bab356867a1c88305bb42080f3b2f0`.
The ten missing product/provenance families, sole backend-only disposition of
`ledger.workspace.read`, explicit OPEN G0 state, and absence of S05 product or
TUI edits remain accurate. The focused suite passed 50 tests in 60.30 seconds.

### diagnostics-proof-provenance | medium | CLI diagnostics coverage is described too narrowly

The corrected count is right, but its explanatory sentence says the existing
diagnostics test merely exercises a CLI-owned projection helper over a prebuilt
report and "does not invoke" `build_llm_diagnostics_report`. The real CLI
integration tests in `test_ledger_llm_diagnostics.py` seed production stores
and transitively execute that report builder through `ledger_llm_diagnostics`;
other tests in the file separately validate the CLI projection models over
prebuilt payloads. Neither is a direct application-symbol test, so
`ledger.llm.diagnostics` correctly remains unproved under the declared census
criterion, but the current provenance sentence conflates the two coverage
shapes and understates the existing end-to-end evidence.

## Recommendations

- Reopen `W01.P02.S05`, correct the direct-proof tally to 55/8 and add
  `ledger.llm.diagnostics` to the exact unproved set, or add a focused direct
  application-level behavioral test of `build_llm_diagnostics_report` in the
  existing diagnostics-aggregation owner
  `src/cadrumo/application/ledger/tests/test_unpriced_cost_reaches_the_operator.py`,
  and keep 56/7 only after that test passes.
- Put the durable proof mapping and positive/defect checks in the Ledger
  application test package so a newly admitted operation, a removed direct
  proof, or a proof attributed only through an adapter fails closed. Then
  refresh the reference, execution record, plan state, digest/index metadata,
  and obtain a new independent review before treating S05 as complete.
- Correct the diagnostics explanation to say that CLI end-to-end tests
  transitively execute the real builder, while no application test directly
  calls its public symbol. This preserves the valid 55/8 disposition without
  erasing real integration coverage.
