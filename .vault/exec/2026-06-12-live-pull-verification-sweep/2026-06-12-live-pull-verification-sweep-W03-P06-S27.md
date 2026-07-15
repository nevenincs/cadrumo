---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-07-10'
step_id: 'S27'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W03.P06.S27 Calendar AEAT Evidence Conflict Projection

Scope: calendar projection hardening for live-backed filed evidence, local Modelo records, justificante verification state, and operator-visible conflict warnings. This records a local projection slice only; the authenticated live exercise required to close `W03.P06.S27` remains open.

## Description

- Preserve disagreeing AEAT filing references when multiple local/live evidence rows describe the same Modelo, year, and typed `Period`.
- Keep the application filing axis separate from the AEAT submission axis when merging Modelo records, filed history observations, and live expediente events.
- Surface `filing.aeat_evidence_conflict` warnings in strict calendar mode and render conflict reference ids in text and JSON output.
- Apply the same strict warning refusal to `--all-profiles` calendar rendering unless `--allow-incomplete` is set.
- Add real repository-backed application and CLI regressions for conflicting local Modelo evidence and AEAT observed/verified evidence.
- Recheck `pull`-only CLI drift guards; no `pull-all` production command was present.

## Outcome

Focused local gates passed:

- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
- `uv run pytest src/aeat/core/tests/test_json_envelope_roundtrip.py src/aeat/core/tests/test_output_rendering.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q`
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/_calendar_models.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/_overview_payloads.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `uv run ruff check src/aeat/locales`
- Locale YAML parse over `src/aeat/locales/*.yml`

## Notes

RAG discovery was attempted with a high timeout and returned `http_search_timeout`, so exact `rg` discovery was used for the scoped slice.

Positive authenticated live censo, filed history, justificante, and calendar aggregation remain open. The local runner still refuses secure-storage access because `AEAT_SECRET_PASSPHRASE` is unset and stdin is noninteractive.

## 2026-07-15 addendum: positive authenticated live evidence closes the projection gap

This addendum supplies the authenticated live evidence this record's original scope
left open. It does not repeat the implementation description above; it records the
verification that the shipped calendar-projection code renders correctly against
real live-pulled data.

### Description

- Reused the operator-present authenticated Cl@ve Móvil session and the filed
  Modelo 303 declarations/expedientes pulled in `S11`/`S12` (2023-2024, real
  `expediente_id`s and casilla data).
- Ran `app overview calendar --from 2023-01-01 --to 2026-12-31 --allow-incomplete`
  and inspected every Modelo 303 calendar entry's `filing_evidence` block.

### Outcome

The calendar entries for Modelo 303 correctly distinguish three states from the
same live-pulled data, proving the local-vs-AEAT-submitted-vs-not-observed axis
this step exists to verify:

- 2024 1T/2T/3T (periods for which `filed pull` captured the declaration
  observation): `aeat_submission_state=justificante_verified`,
  `evidence_source=filed_declaration_observation`, `justificante_verified=true`.
- 2024 4T (a period for which only `expedientes pull` ran, no filed-declaration
  pull): `aeat_submission_state=submitted_observed`,
  `evidence_source=aeat_sede_expedientes`, `justificante_verified=false` — a
  distinct, weaker evidence tier than the periods above.
- 2025/2026 (periods never live-pulled): `aeat_submission_state=not_observed`,
  `evidence_source=null`.
- Every one of the above rows also carries `local_filing_state=not_ready_to_file`
  throughout, because no local calculation was ever run for this identity — proving
  the local-readiness axis and the AEAT-submission axis are genuinely independent
  fields, not a single collapsed status.

This closes the authenticated-evidence gap the original scope left open: the
projection is not just structurally correct against synthetic fixtures (as the
focused pytest gates above already proved) but renders correctly against real
live-pulled AEAT data with a real four-year evidence gradient.

### Notes

Redacted per the sweep convention: only aggregate state names, typed evidence-source
identifiers, and period/year labels are cited; no raw NIE/NIF or session material.
