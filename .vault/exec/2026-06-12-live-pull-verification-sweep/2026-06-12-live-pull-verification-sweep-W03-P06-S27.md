---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
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
