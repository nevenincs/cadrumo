---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
plan: '[[2026-06-12-live-pull-verification-sweep-plan]]'
step_id: W03.P06.S27
related_steps:
  - W04.P07.S29
---

# W03.P06.S27 calendar text evidence details

## Scope

Hardened `aeat app overview calendar` text output so each Modelo calendar row
shows the AEAT evidence identity behind the row, not only the local/AEAT state
and `justificante` boolean.

This improves the operator-facing calendar audit trail for the filing semantic
split:

- local application filing readiness remains visible as `local=...`;
- real AEAT-side state remains visible as `aeat=...`;
- verified justificante state remains visible as `justificante=...`;
- the row now also shows the local filing record id, AEAT reference id, AEAT
  evidence kind, and evidence source whenever those values are present.

## Code changes

- `src/aeat/entrypoints/cli/_overview.py`
  - added `_calendar_filing_evidence_text_fields`;
  - reused it for both single-profile and `--all-profiles` calendar row text
    rendering.
- `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - added a real-repository CLI regression that seeds a current Modelo 303
    filing record plus matching persisted justificante metadata and proves text
    mode exposes:
    - `local=external_baseline_imported`;
    - `aeat=justificante_verified`;
    - `justificante=true`;
    - `local_record=...`;
    - `aeat_ref=...`;
    - `aeat_kind=aeat_justificante_pdf`;
    - `evidence_source=modelo_filing_record`.

No AEAT transport path, live-read gate, or `pull`/`pull-all` command surface was
changed.

## Verification

Required semantic discovery was attempted first:

- `vaultspec-rag search --timeout 180 "justificante enrollment calendar modelo filing state AEAT verified cross period filed history reconciliation"`
  - result: `http_search_timeout`.

Focused local gates:

- `.venv\Scripts\python.exe -m ruff check src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_text_output_names_verified_aeat_evidence -q -rs --tb=short`
  - result: 1 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q -rs --tb=short`
  - result: 14 passed.

## Plan status

This is local/operator-surface hardening for calendar projection evidence. It
does not close `W03.P06.S27` because positive live censo, filed-history, and
justificante data still need to be pulled and projected after successful
operator-mediated AEAT authentication.
