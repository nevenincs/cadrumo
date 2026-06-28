---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: W02.P04.S11,W02.P04.S14,W03.P05.S18,W04.P07.S29
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
---

# Direct Justificante Evidence Conflict Guard

## Scope

This slice closes an asymmetry between filed-history justificante enrollment and
direct live justificante capture enrollment. Filed-history enrollment already
refused to overwrite an existing AEAT evidence reference. Direct
`register_capture_as_filing_evidence` parsed and matched the receipt, but then
unconditionally replaced the filing record's external evidence.

## Implementation

- `register_capture_as_filing_evidence` now refuses to overwrite an existing
  AEAT evidence reference with a different live-capture CSV.
- If the current filing already carries `aeat_justificante_pdf` or
  `aeat_live_capture` for the same CSV, the operation is idempotent: it saves
  the parsed justificante metadata if needed and returns the current filing
  record without rewriting the filing catalogue or emitting another
  `MODELO_LIVE_EVIDENCE_STAMPED` event.
- Added focused regressions using the real Modelo 130 justificante PDF fixture:
  one for idempotent same-CSV behavior and one for refusal on a different
  existing CSV.

## Live Evidence

After AEAT cleared the earlier pending Cl@ve petition:

- `config auth status` reported Cl@ve configured, authenticated, available, and
  aligned to the active profile.
- `app live filed list --modelo 303 --from-year 2026 --to-year 2026` completed
  with `row_count=0` and `failed_count=0`.
- `config profile censo pull` reached AEAT G313 and refused with `AEAT sede
  G313 returned no readable censo for profile <profile-id>`.
- `app live filed pull --modelo 303 --year 2026 --limit 1` completed with
  `captured_count=0`, `justificante_metadata_count=0`, and
  `filing_evidence_stamped_count=0`.
- `app overview calendar --from 2026-01-01 --to 2026-12-31
  --allow-incomplete` still returned seven Modelo entries, one AEAT message
  event, no observed AEAT filing evidence, no verified justificantes, and
  `censo.enrolment_unverified`.

The live filed CLI/backend path is operational, but this account state still has
no filed Modelo 303 row to download, parse, and enroll as positive official
justificante evidence.

## Verification

- `python -m ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py` passed.
- `python -m pytest -m "unit or integration" src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q` passed: 14 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/live/tests/test_filed_capture_calculation_history.py -q` passed: 20 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_import_flow.py -q` passed: 57 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q` passed: 80 passed.
- `python -m pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q` passed: 2 passed.

## Open Rows

- `W02.P04.S10` remains open because G313 still returns no readable censo.
- `W02.P04.S11` has live list and single pull proof for Modelo 303/2026, but
  remains open for positive filed-row, all-model, source-pull, and persisted
  official evidence proof.
- `W02.P04.S14` has stronger local direct-capture enrollment proof, but remains
  open for positive authenticated justificante pull from AEAT.
- `W03.P05.S18` remains open for broader filed CLI JSON/text and positive row
  evidence, although `pull` and no-`pull-all` behavior are verified.
