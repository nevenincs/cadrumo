---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S28'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W03.P03.S28 - Censo-apply calendar obligation rows

## Description

- Expose concrete calendar obligation rows from `config profile censo apply` after censo facts derive the taxpayer model.
- Keep JSON and text output aligned on filing year, typed registry period token, opening date, statutory close date, adjusted close date, payment cutoff, filing status, and user state.
- Assert that censo-derived taxpayer axes produce a concrete Modelo 303 filing window rather than only proving that a Modelo 303 obligation exists.

## Outcome

`CensoApplyPayload` now carries `calendar_obligation_rows`, populated from the rebuilt overview calendar after the censo apply operation reloads the reconciled profile. Each row records `modelo`, `filing_year`, `period`, `opens_on`, `closes_on`, `adjusted_closes_on`, `payment_cutoff_on`, `status`, and `user_state`.

Text mode now emits the same obligation fields in each `calendar_obligation` line using a stable tab-delimited command surface. JSON mode exposes the same rows through the typed payload.

The censo sync test now proves that NIE plus IAE-derived taxpayer axes feed the calendar into a concrete Modelo 303 1T 2025 window with `opens_on = 2025-04-01` and `closes_on = 2025-04-21`. CLI tests parse real text output and JSON output for a current-year Modelo 303 row and verify deadline ordering plus payment/state fields.

## Verification

- `vaultspec-rag search --timeout 600 "censo apply calendar_obligation_rows CLI text output status user_state payment_cutoff_on"` returned the live-censo plan, prior censo-calendar execution notes, and deadline-engine ADR grounding.
- `uv run ruff check src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/_config/_profile_censo_payloads.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/application/user_profile/tests/test_censo_sync.py` passed.
- `uv run pytest src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -q` passed with 17 selected tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "integration or not integration" -q` passed with 103 tests.
- `uv run pytest src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/application/overview/tests/test_calendar_taxpayer_model.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 42 tests.
- `vaultspec-code-reviewer` reviewed S28, identified CENSO-026 in the first pass, and returned PASS after the text CLI surface was hardened. The post-review JSON assertion gap was then closed locally.

## Live Verification Status

This step hardens the local censo-to-calendar projection and CLI contract. Full live G313 proof remains a separate open plan item: it requires creating or selecting a profile whose tax ID matches the identity used during AEAT authentication, then running live censo pull, apply, filed-history pull, notifications pull, justificante reconciliation, and final calendar projection.
