---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:eff37d2518799f6a1f125a1914c618d367b5c6e7e42b7816eabe5c3c22651d54'
step_id: 'S25'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add a calendar backend fixture variant that omits chosen gating profile facts instead of answering them

## Scope

- `src/cadrumo/entrypoints/cli/tests/_overview_calendar_support.py`

## Description

- Added `calendar_backend_omitting_gating_facts`, taking the fact paths to leave unanswered and overriding each to the empty string, which the profile registration helper drops rather than stores.
- Left the existing shared backend untouched, since peer scenario fixtures depend on it answering every gating fact.
- Made the helper refuse a path the default backend does not answer, rather than silently accepting it.

## Outcome

The fixture layer can now express an operator who has not answered a gating question yet, which the existing backend could not.

The distinction the helper turns on is absence versus present-and-false. The default backend sets every gating fact to `"false"`, which is an ANSWER, and the completeness warning fires only on an unanswered fact. Overriding to the empty string is what produces genuine absence, because the registration helper filters out empty values before building facts.

The guard against unknown paths matters more than it looks: a typo in a fact path would otherwise produce a fixture identical to the default one, and every test built on it would pass while proving nothing. Refusing loudly converts that silent no-op into an immediate failure.

A new helper was added rather than the shared one parameterised, because the shared backend is used by peer scenario fixtures that rely on the generic completeness gate staying quiet.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_end_to_end.py -m integration -n 0 -q
    14 passed in 21.19s

The helper's effect is proven by the control test in that module, which runs it with nothing omitted and confirms the refusal disappears.

## Notes

Not autouse-friendly by design: the active-profile pointer transaction refuses to nest across storage roots, so a module cannot open a second backend inside an autouse one. Recorded in the consuming module's fixture docstring.
