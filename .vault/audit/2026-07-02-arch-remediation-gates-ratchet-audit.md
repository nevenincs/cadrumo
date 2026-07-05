---
tags:
  - '#audit'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-07-02-arch-remediation-gates-ratchet-plan]]"
---

# `arch-remediation-gates-ratchet` audit: `implementation review`

## Scope

Review of the repaired Import Linter ledger, the new ledger ratchet tests, and
the vault execution records for the gate-ledger repair plan. The review checked
that the broad application-to-adapters wildcard is absent, the remaining
module-level pins resolve on disk, the count-ratchet baselines match the
post-repair ledger, no plan metadata was added to runtime test code, and the
required gates run cleanly.

## Findings

No open findings.

### follow-up-profile-activity-test-boundary | low | application test no longer imports CLI test helpers

Reviewed the 2026-07-05 ratchet follow-up that rewired
`test_review_profile_activity_staleness` away from the CLI test-support
package. The test still provisions a real encrypted profile bucket and mutates
the relation-scoping `activities.description` fact through application
profile primitives; it no longer adds an application-to-entrypoints edge to the
layered contract. Focused pytest passed, and the layered linter rerun no longer
reports an application-to-entrypoints violation. The layered contract remains
red on the broader application-to-adapters inventory, so this is a boundary
reduction only, not program closure.

### follow-up-error-class-registration-boundary | low | application test no longer imports AEAT auth adapter

Reviewed the 2026-07-05 ratchet follow-up that rewired
`test_error_class_registration` away from the outbound AEAT auth adapter. The
certificate probe still builds a real PKCS#12 bundle and calls the application
`probe_provider_configuration` surface; the assertion now observes the
propagated `AeatError` through the registered `AUTH_AUTH_VALIDATION` code
instead of importing the adapter exception class. Focused pytest and ruff
passed. The layered linter rerun no longer reports
`application.tests.test_error_class_registration`, but the importlinter ledger
count remains above baseline at 850, so this is a targeted boundary cleanup
only.

### follow-up-ledger-import-errors-boundary | low | application ledger test uses local test support re-export

Reviewed the 2026-07-05 ratchet follow-up that removed the direct SQL storage
adapter import from `test_actions_import_errors`. The test continues to use
the real `SecureObjectRepository`, now obtained through the existing
`application.ledger.tests._action_test_support` support surface that the
neighboring ledger action tests already use. Focused pytest and ruff passed.
The layered linter rerun no longer reports
`application.ledger.tests.test_actions_import_errors`, but the importlinter
ledger count remains above baseline at 850, so this is another targeted
boundary cleanup only.

### follow-up-renta-classifier-size-budget | low | Renta expense classifier below callable budget

Reviewed the 2026-07-05 ratchet follow-up that extracted the repeated
`RentaLedgerAggregationIssue` envelope construction from
`_classify_renta_transaction` into `_renta_transaction_issue`. The classifier's
branch ordering, reason codes, and detail strings remain unchanged; the callable
line count dropped from 190 to 164, below the default 180-line budget. Focused
Renta aggregation tests and ruff passed. The codebase-size gate rerun no longer
reports `_classify_renta_transaction`, but it remains red on the other known
module and callable offenders.

### follow-up-evidence-confirm-size-budget | low | evidence confirm callable below budget

Reviewed the 2026-07-05 ratchet follow-up that extracted invoice-date
resolution from `confirm_invoice_draft_from_evidence` into
`_resolve_confirmed_invoice_date`. The confirm flow still reuses the same draft
value, preserves the same missing-date refusal text and suggestion, and
delegates the catalogue write unchanged. The callable line count dropped from
183 to 175, below the default 180-line budget. Focused evidence-draft tests and
ruff passed. The codebase-size gate rerun no longer reports
`confirm_invoice_draft_from_evidence`, but remains red on the other known
module and callable offenders.

### follow-up-m145-cli-size-budget | low | M145 registration callable below budget

Reviewed the 2026-07-05 ratchet follow-up that moved the Modelo 145
state-transition Typer command closures from `register_m145_communication_commands`
into `_register_m145_transition_commands`. The command names, help text, actor
resolution, active-bucket guard, and emitted payload operations remain unchanged.
The registration callable line count dropped from 185 to 139, below the default
180-line budget. Ruff passed, and the M145 CLI integration suite passed with
`-m integration`. The codebase-size gate rerun no longer reports
`register_m145_communication_commands`, but remains red on the other known
module and callable offenders.

### follow-up-amendment-action-size-budget | low | amendment workflow callable below budget

Reviewed the 2026-07-05 ratchet follow-up that extracted amendment draft
revision construction and filing-catalogue supersession updates from
`amend_modelo_revision` into `_build_amendment_draft_revision` and
`_build_amendment_filing_updates`. The public workflow still performs the same
baseline loading, amendment-kind guards, registry completeness gate,
verification/filed transitions, and side-effect persistence in the same order.
The callable line count dropped from 197 to 173, below the default 180-line
budget. Ruff passed, and the focused amendment flow/kind-resolution suites
passed. The codebase-size gate rerun no longer reports `amend_modelo_revision`,
but remains red on the other known module and callable offenders.

### follow-up-ledger-evidence-confirm-size-budget | low | evidence confirm CLI callables below budget

Reviewed the 2026-07-05 ratchet follow-up that moved the
`evidence_confirm` command body into `_run_evidence_confirm`, leaving the Typer
handler as a parameter bridge. The command still validates exactly-one evidence
reference, delegates to `confirm_invoice_draft_from_evidence`, renders the same
payload rows, and emits the same idempotent/next-action notices. The
`_register_evidence_confirm_command` callable dropped from 211 to 125 lines and
`evidence_confirm` dropped from 203 to 117, both below the default 180-line
budget. Ruff passed, and the real evidence-confirm CLI integration suite passed
with `-m integration`. The codebase-size gate rerun no longer reports either
ledger evidence confirm callable, but remains red on the other known module and
callable offenders.

### follow-up-review-package-build-size-budget | low | review-package build callable below budget

Reviewed the 2026-07-05 ratchet follow-up that extracted review-package build
payload/line projection into the new `_modelo_review_package_rendering` module.
The `review_package_build` command still resolves the target revision, exports
the fichero-BOE draft, builds the package, and emits the same envelope shape;
only the final result projection moved out of the oversized CLI module. The
callable line count dropped from 199 to 179, below the default 180-line budget,
and the CLI module line count dropped from 1349 to 1332. Ruff passed, the real
review-package CLI integration suite passed with `-m integration`, and the new
rendering module is reachable from existing tests. The codebase-size gate rerun
no longer reports `review_package_build`, but remains red on the other known
module and callable offenders.

### follow-up-mcp-build-server-size-budget | low | MCP server builder below pinned budget

Reviewed the 2026-07-05 ratchet follow-up that hoisted the optional telemetry
forwarder out of `build_server`. The server still constructs the same
persona-scoped tool list, meta/floor/grounding tools, prompt handlers, resource
handlers, confirmation routes, faithfulness gate, and telemetry rows; only the
thin optional sink forwarding helper moved to module scope. The `build_server`
callable line count dropped from 355 to 337, below its pinned 341-line budget.
Ruff passed, and the real MCP server integration tests covering meta-tools,
serving gates, persona wiring, and client handshake passed with
`-m integration`. The codebase-size gate rerun no longer reports
`build_server`, but remains red on the other known module and callable
offenders.

### follow-up-ledger-bindings-module-size-budget | low | ledger bindings below module budget

Reviewed the 2026-07-05 ratchet follow-up that removed standalone decorative
separator comments from `_ledger_bindings.py` while preserving all section
headings, explanatory domain comments, public exports, selectors, validators,
and resolver logic. The module line count dropped from 1404 to 1395, below its
1400-line budget. Ruff passed, and the focused registry suites covering public
API boundaries, selector shapes, OSS/IOSS aggregation, IVA aggregation, and
annual IVA aggregation passed. The codebase-size gate rerun no longer reports
`_ledger_bindings.py`, but remains red on the other known module and callable
offenders.

### follow-up-modelo-reconcile-module-size-budget | low | reconcile module below budget

Reviewed the 2026-07-05 ratchet follow-up that tightened the
`_DECLARATION_CASILLA_RECONCILE_MODELOS` explanatory docstring without changing
the enrolled modelo set, the declaration-source refusal contract, or any
reconcile logic. The module line count dropped from 1254 to 1246, below its
1250-line budget. Ruff passed, and the real reconcile service/CLI tests covering
justificante reconciliation, declaration casilla reconciliation, multi-modelo
enrollment, value comparison, and CLI behavior passed. The codebase-size gate
rerun no longer reports `_reconcile.py`, but remains red on the other known
module and callable offenders.

### follow-up-transaction-models-module-size-budget | low | transaction models at module budget

Reviewed the 2026-07-05 ratchet follow-up that tightened top-level and catalogue
docstrings in `domain/transactions/_models.py` without changing the transaction
models, validators, serializers, catalogue behavior, or public exports. The
module line count dropped from 1353 to 1340, matching its 1340-line budget. Ruff
passed, and the full domain transaction test suite passed. The codebase-size
gate rerun no longer reports `domain/transactions/_models.py`, but remains red
on the other known module and callable offenders.

## Recommendations

Keep the `aeat.tests.secure_sql -> aeat.adapters.**` wildcard under explicit
review in later inversion work. It remains justified here because the helper is
a shared secure-storage test utility that imports real persistence adapters.
