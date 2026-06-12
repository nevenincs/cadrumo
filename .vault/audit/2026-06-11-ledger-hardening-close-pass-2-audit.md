---
tags:
  - '#audit'
  - '#ledger-hardening-close'
date: '2026-06-11'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
  - '[[2026-06-11-ledger-hardening-close-audit]]'
---

# `ledger-hardening-close` audit: `close honesty review pass 2`

## Scope

Fresh inherited-state review after commit `da5b1c5e0`, which retired the C4 `AggregationSourceKind.INVOICE` alias and reconciled the C4 plan from 23/30 to 29/30.

## Findings

### HIGH - Full-tree collection is still not green

The C4 alias-retirement implementation is verified by focused lint, aggregation/operator/registry tests, API-stub conformance, documented-command conformance, and JSON schema conformance. The exact C4 full collect-only gate remains open: `uv run --no-sync pytest --collect-only -q src/aeat` currently collects 14,689 selected tests and stops with 20 collection errors before a green full-tree answer is possible.

Tracking: `P04.S24` remains open in `2026-06-10-ledger-invoice-unification-plan`, with the current failure signature recorded in the S24 exec note.

### MEDIUM - Remaining collection failures are outside the C4 alias-retirement surface

The current collection errors are support-module export splits and peer campaign drift: declaracion verification-chain support, AEAT auth support, secure-object support, runtime migrated repository support, ledger action support, modelo file-flow support, registry referential/schema support, `_validate_semantic_roles`, and `LedgerPeriodPayload`. These are not introduced by the C4 alias deletion and should not be patched opportunistically from the ledger close pass.

Tracking: do not create C4 implementation steps for these; wait for owning campaigns or route to their active plans.

### LOW - C4 alias-retirement claim is now structurally backed

The prior close audit's C4 HIGH finding is no longer current. `AggregationSourceKind.INVOICE` has been removed, production `src/aeat` has no remaining references, the operator taxonomy now matches the core taxonomy exactly, and registry invoice-shaped validation routes through canonical invoice source kinds.

Tracking: C4 remains open only because `P04.S24` is a full-tree verification gate and the tree is not currently collect-clean.

## Recommendations

- Treat C4 authoring as complete except for the full-tree collect-only gate.
- Do not mark the ledger hardening epic structurally complete until `P04.S24` can be checked green or formally deferred by a follow-up campaign that owns the repository-wide support-split cleanup.
- Continue using focused green ledger gates while the shared factory tree is in peer churn.

## Codification candidates

- **Source:** HIGH finding above. **Rule slug:** `full-tree-gate-must-distinguish-owner`. **Rule:** When a required full-tree gate is red, record the exact current failure signatures and distinguish owner-surface failures from unrelated factory churn before marking a feature step complete.

## Pass 3 Update

### RESOLVED - Full-tree collection is green

The exact C4 full collect-only gate now exits 0: `uv run --no-sync pytest --collect-only -q src/aeat` collected `15101/16882` tests with `1781` deselected. The previous support-module split blockers have settled or been reconciled, and `P04.S24` is now checked closed in the ledger invoice unification plan.

### VERIFIED - CLI conformance and period grammar sweeps are green

The documented-command conformance gate passed `41/41` under both `-m integration` and `-m "integration or not integration"`. The JSON schema conformance gate passed `92/92` under `-m "integration or not integration"`. The period/fx/list-filter reconciliation sweep passed `62/62` under `-m "integration or not integration"`, covering the remaining `fx_import` and period grammar surfaces named in the handover.

### INFO - Residual factory churn remains unrelated

After the closeout commits, the worktree still carries unrelated peer edits in source files outside the ledger invoice closeout path. These were not staged or committed by this pass.

## Pass 4 Update

### VERIFIED - C5 deferred remainder is now structurally closed

The ledger interface contract plan now has every row checked closed, including the previously deferred `W02.P02` positional-id work and the `W03.P05` typed-payload remainder. The C5 exec directory contains records for `S01` through `S32`; the earlier review concern about missing `S05` through `S09` peer records is resolved.

### VERIFIED - C5 owner-surface gates are green

The focused C5 completion gate passed `79/79`: transaction roundtrip, ledger verb spine, documented-command conformance, typed interface payloads, and ledger list sort. The C5 ledger CLI files also pass both owner-surface type checks: `ty check` reports `All checks passed!`, and `pyright` reports `0 errors, 0 warnings, 0 informations`.

### OPEN - Repository-wide default test lane is not closable from ledger

The default full-suite lane was started with `uv run --no-sync pytest src/aeat -q` and progressed to 40 percent before the 15-minute foreground tool timeout. The partial log had already surfaced a non-ledger failure in `src/aeat/core/errors/tests/test_exception_base_hygiene.py`. Replaying that test directly fails because `src/aeat/core/_period.py` defines `PeriodError(ValueError)`, which violates the production exception root hygiene gate.

Tracking: this is a core-period exception-hygiene issue, not a ledger hardening implementation issue. Do not close the full default lane as green until the owning period/core campaign resolves or records that exception root.

### OPEN - Explicit integration-or-not full lane is blocked before ledger

The explicit lane `uv run --no-sync pytest src/aeat -m "integration or not integration" -q -x` fails before reaching ledger with `fixture '_settings_factory' not found` in `src/aeat/adapters/outbound/aeat/auth/tests/test_authenticator_part1.py::test_invalid_persisted_session_redacts_path_and_reason`. The fail-fast run reached `887 passed, 2 skipped` before that auth fixture error.

Tracking: this is an outbound AEAT auth test fixture issue, not a ledger hardening implementation issue. It remains a campaign-close blocker for repository-wide green, but not an owner-surface blocker for C1-C7 ledger authoring.

### OPEN - Repository-wide type harness remains baseline red

`just check-types` currently reports `769 diagnostics` (`407 ty`, `362 pyright`) concentrated in calculation/modelo test surfaces. Focused type checks over the C5 ledger CLI payload and emit files are clean, so the global red is tracked as shared factory baseline rather than a ledger-interface-contract regression.

## Pass 5 Update

### RESOLVED - Early full-lane blockers repaired

Four repository-wide blockers that prevented the close sweep from reaching ledger were repaired in this pass:

- `PeriodError` now participates in the registered `AeatError` hierarchy while preserving `ValueError` compatibility.
- The private unresolved-formula sentinel is explicitly documented in the exception-hygiene allowlist because it is caught inside the formula runtime and never crosses a public boundary.
- `ModeloLocaleError` is registered as a locale-manager AEAT error while preserving `ValueError` compatibility.
- The IVA wallet no-auth path refuses before touching typed period fields, preserving the translated no-auth error contract.
- Sede observation-store tests now construct real `Period` values instead of string periods.
- Google pull metadata matching compares period token to period token, so aligned workbook metadata classifies as `matches`.

Focused verification passed after these repairs: exception hygiene / registry / period / modelo-locale tests passed `100/100`; the Sede auth-state no-session test passed `1/1`; Sede observation-store tests passed `2/2`; Google pull adapter helper tests passed `19/19`; and the C5 ledger completion gate remained green at `79/79`.

### OPEN - Explicit integration-or-not full lane now blocks in storage runtime migration

After the repairs above, `uv run --no-sync pytest src/aeat -m "integration or not integration" -q -x` advances to `2570 passed, 32 skipped` before failing in `src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories_part1.py::test_workflow_state_default_isolates_active_profile_writes`. The assertion still expects declaration key `303:bucket-b`, while the loaded workflow state now carries the canonical period-qualified key `303:2026:1T`.

Tracking: this is a storage/workflow runtime-migration test expectation drift, not a ledger hardening implementation issue. It is now the first known repository-wide closeout blocker after the ledger and early shared blockers are cleared.
