---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S32'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W03.P03.S32 - Per-Modelo censo enrolment provenance

## Description

- Replace profile-level-only censo provenance on each censo-apply calendar obligation row with per-Modelo filtered provenance.
- Derive the relevant profile keys from the overview/calendar applicability boundary, not from duplicated CLI rule logic.
- Preserve the full censo enrolment source list in the summary while narrowing each row's `enrolment_source_paths`.

## Outcome

`calendar_applicability_profile_keys_for_modelo(modelo)` now exposes the profile keys that can influence a Modelo's calendar applicability. It is derived from the canonical modelo applicability rule table plus the existing IVA gating set.

`config profile censo apply` now uses that helper when building each `calendar_obligation_rows` item. If a row depends on `taxpayer_type.irpf_income_categories`, the supporting raw censo fact `activities.iae_epigraph` is included as provenance because it is what justified deriving the economic-activity income category.

The summary still reports the full censo enrolment source set. Individual rows are narrower:

- Modelo 303 carries `activities.iae_epigraph=aeat_censo_read`, `taxpayer_type.entity_type=aeat_censo_derived`, and `taxpayer_type.irpf_income_categories=aeat_censo_derived`.
- Modelo 100 carries only `taxpayer_type.entity_type=aeat_censo_derived`.

## Verification

- `vaultspec-rag search --timeout 600 "calendar applicability per modelo profile keys dependency required keys censo enrolment provenance defaulted_modelos CalendarCompleteness"` returned the canonical applicability authority trail.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/__init__.py src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py` passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 11 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_taxpayer_model.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 27 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 103 tests.
- `uv run pytest src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/application/overview/tests/test_calendar_taxpayer_model.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 53 tests.
- `vaultspec-code-reviewer` reviewed S32 and returned PASS; CENSO-029 records the review.

## Live Verification Status

This is local censo/calendar provenance hardening. Full live G313 and justificante proof remains gated on a real matching taxpayer profile and unlock passphrase.
