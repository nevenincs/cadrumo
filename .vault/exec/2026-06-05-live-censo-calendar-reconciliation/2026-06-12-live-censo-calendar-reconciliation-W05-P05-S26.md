---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S26'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S26 - ModeloRecord AEAT acceptance evidence invariant

## Description

- Enforce at the domain boundary that `ModeloRecord.aeat_accepted` cannot be true without `external_evidence`.
- Close the Pydantic v2 `model_copy(update=...)` validator bypass for updated `ModeloRecord` instances.
- Keep downstream calendar and cross-period defensive handling for corrupt legacy records explicit.

## Outcome

`ModeloRecord` now rejects AEAT acceptance without an external evidence reference during construction and during normal copy-update operations. Updated copies are revalidated through `model_validate`, so production paths that stamp live evidence must provide the evidence and the acceptance bit together.

Calendar and cross-period tests that intentionally exercise corrupt historical records now use `model_construct` explicitly. That keeps the defensive-read behavior testable without leaving normal domain APIs able to create the invalid state.

## Verification

- `uv run ruff check src/aeat/domain/modelos/_filing_record.py src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py` passed.
- `uv run pytest src/aeat/domain/modelos/tests/test_filing_record_repository_roundtrip.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` passed with 106 tests.
- `uv run pytest src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_amend_flow.py -q` passed with 60 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 63 tests.
- `vaultspec-rag search --timeout 300 "ModeloRecord aeat_accepted external_evidence calendar justificante Period typed pull CLI verb drift"` returned the live-censo S14/S15 pull-only and typed Period records plus the calendar filing semantics references.
- `vaultspec-code-reviewer` re-reviewed the S26 fix and returned PASS.

## Live Verification Status

The isolated live smoke storage root `var/live-user-smoke/20260612-s26` is unlocked with a file-backed passphrase and is empty. The CLI can render `config profile create --help`, `app live --help`, and `config profile list` under that isolated storage.

The full live censo/filed/messages/calendar sequence still needs a profile tax identifier that matches the authenticated taxpayer. The CLI requires `config profile create NAME --tax-id ...` before `config profile censo pull`; without the matching NIF/NIE/CIF the live censo reconciliation would either fail closed or produce non-actionable identity-mismatch evidence.
