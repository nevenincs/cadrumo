---
step_id: S429
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W05.P23.S429-S443 — locale regression fix + translated_message sweep

## Outcome

Landed 15 Steps (S429-S443) in a single-agent pass over the workflow, auth, and core locale surfaces.

**S429 regression fix**: `_persistence.py:105` `WorkflowError` now routes through `translated_message=` instead of positional `tr()`. The prior `tr()` call resolved at raise time against the invoking thread's locale, not at render time against the operator's configured output language. Removed the now-unused `tr` import from `_persistence.py`.

**W4-new-class threadings (S430-S432)** explicitly called out:
- S430: `SessionDeserializationError` at `_sessions.py:419` — `translated_message="application.auth.errors.session_field_not_datetime"` with `{"field": field}` context.
- S431: `AuthProviderReservedError` at `_operator.py:1215` — `translated_message="application.auth.errors.provider_reserved"` with `{"provider": provider}` context.
- S432: `ProfileRegistrationError` at `core/profile.py:92` — `translated_message="core.profile.errors.registration_duplicate_callable"`. (Keys already present in HEAD from concurrent W05.P24 campaign — idempotent set.)

**Remaining threadings**: S433 (ProfileLabelAmbiguousError), S434 (4 WorkflowResumeRefusedError sites), S435 (state-write-invalid-payload), S436 (run-not-found), S437 (period-registry x 2), S438 (no-run-for-period), S439 (3 adapter-missing), S440 (run-id-invalid x 2), S441 (f-string key in _google.py converted to translated_message= + context).

**S442**: `test_flow_description_keys.py` inventory test asserting all registered WIZARD_FLOWS have `wizard.{flow.id}.description` locale keys across 4 catalogues.

**S443**: `test_w05_p23_locale_coverage.py` aggregate test — 76 parametrized assertions across 19 keys x 4 locales pass.

## Files touched

- `src/aeat/application/workflow/_persistence.py`
- `src/aeat/application/workflow/_resume.py`
- `src/aeat/application/workflow/_engine.py`
- `src/aeat/application/workflow/_adapters.py`
- `src/aeat/application/workflow/_profile_bucket_scan.py`
- `src/aeat/application/auth/_sessions.py`
- `src/aeat/application/auth/_operator.py`
- `src/aeat/entrypoints/cli/_config/_google.py`
- `src/aeat/test_w05_p23_locale_coverage.py` (new)
- `src/aeat/application/wizard/test_flow_description_keys.py` (new)

## Locale keys (19 new, set across en/es/ca/hu)

`application.workflow.errors.*`: state_write_invalid_payload, run_not_found, run_id_invalid_separators, run_id_invalid_blank, resume_refused_not_aborted, resume_refused_no_aborted_reason, resume_refused_terminal_reason, resume_refused_no_obligation, no_run_for_period, period_registry_year_unresolvable, period_registry_unmappable, profile_label_ambiguous, adapter_missing_deadline_engine, adapter_missing_filing_draft_builder, adapter_missing_inputs_provider.
`application.auth.errors.*`: session_field_not_datetime, provider_reserved.
`core.profile.errors.*`: registration_duplicate_callable.

## Test result

258 tests pass (80 from S443 + 4 from S442 + engine + prior inventory suite).

## Commit

ec73b9f2f — locale(W05.P23.S429-S443): translated_message sweep + regression fix + locale coverage
