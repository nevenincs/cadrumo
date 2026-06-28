---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S31'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W03.P03.S31 - Censo-derived enrolment provenance on calendar rows

## Description

- Make censo-apply calendar rows prove that obligation enrolment became computable from censo-derived taxpayer-model facts.
- Preserve operator-visible provenance without exposing raw censo values in the text summary.
- Keep JSON and text censo-apply surfaces aligned.

## Outcome

`config profile censo apply` now reloads the reconciled profile after applying the censo snapshot and extracts censo-stamped enrolment provenance from the profile facts. The summary includes `calendar_enrolment_source_paths`, and every `calendar_obligation_rows` item carries the same `enrolment_source_paths` list.

Text output emits:

- `calendar_enrolment_sources`;
- `enrolment_sources=...` on each `calendar_obligation` row.

The covered natural-person economic-activity path proves:

- `activities.iae_epigraph=aeat_censo_read`;
- `taxpayer_type.entity_type=aeat_censo_derived`;
- `taxpayer_type.irpf_income_categories=aeat_censo_derived`.

This makes the censo-derived legal-situation bridge visible in the same CLI surface that reports concrete calendar filing windows.

## Verification

- `vaultspec-rag search --timeout 600 "censo derived profile facts obligation enrolment calendar source evidence taxpayer model declared live censo reconciliation S06 S07"` returned the live-censo plan and S06/S07 execution/audit context.
- `uv run ruff check src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/_config/_profile_censo_payloads.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py` passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 11 tests.
- `uv run pytest src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 28 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 103 tests.
- `uv run pytest src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/application/overview/tests/test_calendar_taxpayer_model.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 42 tests.
- `vaultspec-code-reviewer` reviewed S31 and returned PASS; residual risk is that this is profile-level provenance, not a per-modelo dependency graph, and live G313 proof remains separate.

## Live Verification Status

This step is local backend/CLI hardening. Full live G313 proof still requires a profile tax ID matching the AEAT identity used during authentication and a valid profile passphrase.
