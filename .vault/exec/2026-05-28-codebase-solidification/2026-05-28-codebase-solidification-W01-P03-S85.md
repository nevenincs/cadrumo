---
step_id: S85
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S85-S96 — verification-finding cluster localisation

## Scope

Single-agent execution of the full S85-S96 cluster in `src/aeat/application/modelo/_actions.py`.
All six finding message/next_action pairs were routed through `tr()` in one coordinated edit
to avoid collisions on the heavily-contended file.

## Changes made

### `src/aeat/application/modelo/_actions.py`

- **S85/S87** `_evaluate_verification_predicates` (line ~2633): replaced raw f-string
  `f"cross-casilla invariant {predicate.predicate_id!r} violated: {predicate.expression}"` with
  `tr("application.modelo.findings.cross_casilla_invariant_violated", predicate_id=..., expression=...)`.
  Replaced `next_action` f-string with `tr("application.modelo.findings.cross_casilla_invariant_next_action", predicate_id=...)`.

- **S89** `_collect_revision_verification_findings` (line ~2873): replaced raw f-string for
  registry-snapshot miss with `tr("application.modelo.findings.registry_snapshot_unresolved", modelo=..., filing_year=..., period=...)`.

- **S91** `_dt12_reduccion_advisory_finding` (line ~2957): replaced five-line raw f-string with
  `tr("application.modelo.findings.dt12a_reduccion_possible", ingreso_id=..., ingreso_value=..., reduccion_id=...)`.

- **S93** `_iva_wallet_blocking_verification_finding` (line ~2999): replaced hardcoded
  `next_action` string with `tr("application.modelo.findings.iva_wallet_next_action")`.

- **S95** `_iva_wallet_blocked_message` body: replaced raw f-string with
  `tr("application.modelo.errors.iva_wallet_blocked", divergence=..., reason=...)`.
  Raise site in `_raise_if_persisted_iva_compensation_decision_blocks_work_unit` now also passes
  `translated_message="application.modelo.errors.iva_wallet_blocked"`.

### `src/aeat/locales/en.yml` + `es.yml` + `ca.yml` + `hu.yml`

Six new locale keys added via `python -m aeat.locales set`:
- `application.modelo.findings.cross_casilla_invariant_violated`
- `application.modelo.findings.cross_casilla_invariant_next_action`
- `application.modelo.findings.registry_snapshot_unresolved`
- `application.modelo.findings.dt12a_reduccion_possible`
- `application.modelo.findings.iva_wallet_next_action`
- `application.modelo.errors.iva_wallet_blocked`

All four locales have real authored values (not self-referencing placeholders).
Locale audit: `ca.yml: ok  en.yml: ok  es.yml: ok  hu.yml: ok`.

### `src/aeat/application/modelo/test_actions.py`

Eight new real-behavior tests (S86/S88/S90/S92/S94/S96 pairs):
- `test_cross_casilla_invariant_violated_message_is_localised` — calls `_evaluate_verification_predicates` with a BLOCKING_RULE predicate and violated casilla values; asserts predicate_id and expression appear in the rendered message.
- `test_cross_casilla_invariant_next_action_is_localised` — same setup; asserts predicate_id appears in next_action.
- `test_registry_snapshot_unresolved_finding_is_localised` — calls `_collect_revision_verification_findings` with real WorkUnit/CalculationRevision against non-existent modelo "999"; asserts modelo/year/period tokens in the finding message.
- `test_dt12_reduccion_advisory_message_is_localised` — calls `_dt12_reduccion_advisory_finding` with SimpleNamespace revision carrying the two required semantic roles; asserts ingreso_id, ingreso_value, reduccion_id appear in the message.
- `test_iva_wallet_blocking_finding_next_action_is_localised` — calls `_iva_wallet_blocking_verification_finding` with a real `IvaCompensationReconciliationDecision`; asserts next_action is non-empty, not the raw key, and contains "303".
- `test_iva_wallet_blocked_message_is_localised` — calls `_iva_wallet_blocked_message` with a SimpleNamespace decision; asserts divergence and reason tokens appear in the rendered message.
- `test_iva_wallet_blocked_exception_carries_translated_message_key` — constructs `ModeloIvaWalletReconciliationBlocked` the same way the raise site does post-S95; asserts `exc.translated_message == "application.modelo.errors.iva_wallet_blocked"`.

No mocks, no patches, no skips, no xfail. All 11 tests in the file pass.

## Verification

- `pytest src/aeat/application/modelo/test_actions.py -xvs`: **11 passed**.
- `python -m aeat.locales audit`: **ca.yml: ok  en.yml: ok  es.yml: ok  hu.yml: ok**.
- `ruff check` on both files: clean after auto-fix of import ordering.
- Code review (inline vaultspec-code-reviewer): all six gates pass.
