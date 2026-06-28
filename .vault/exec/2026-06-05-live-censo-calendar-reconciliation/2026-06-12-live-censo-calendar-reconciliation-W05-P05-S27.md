---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S27'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S27 - External evidence requires AEAT acceptance

## Description

- Reject `ModeloRecord.external_evidence` unless the filing record is also `aeat_accepted`.
- Revalidate the same invariant through `ModeloRecord.model_copy(update=...)`.
- Keep calendar projection fail-closed for explicitly constructed legacy/torn records with evidence but no AEAT acceptance.
- Align CLI filing-record rendering fixtures so evidence-bearing records model real imported AEAT evidence.

## Outcome

`ModeloRecord` now has a symmetric evidence invariant: AEAT acceptance requires external evidence, and external evidence requires AEAT acceptance. Normal domain construction and copy-update paths cannot create half-stamped records on either side.

The overview calendar no longer lets a corrupt legacy filing record with `external_evidence` but `aeat_accepted = false` upgrade to `accepted`, `submitted_observed`, or `justificante_verified`. It remains visible as an external-baseline local state only.

Production evidence writers already satisfy the invariant. External import builds the filing record with `aeat_accepted = true` and `external_evidence` together, and live justificante stamping updates both fields in one validated copy operation.

## Verification

- `vaultspec-rag search --timeout 600 "AEAT accepted external evidence without accepted flag calendar cross period justificante ModeloRecord invariant"` returned the calendar filing semantics ADR and cross-period clean-state research as grounding.
- `uv run ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py` passed.
- `uv run pytest src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/entrypoints/cli/tests/test_modelo.py -m "integration or not integration" -q` passed with 235 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 63 tests.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-05-live-censo-calendar-reconciliation-plan.md` passed.
- `vaultspec-code-reviewer` reviewed S27 and returned PASS.

## Live Verification Status

This step is local backend hardening. The full W04 live censo proof still requires creating a fresh isolated profile whose `--tax-id` matches the taxpayer identity used during authentication, then rerunning censo pull, filed pull, expedientes pull, notifications pull, justificante pull, and final calendar projection.
