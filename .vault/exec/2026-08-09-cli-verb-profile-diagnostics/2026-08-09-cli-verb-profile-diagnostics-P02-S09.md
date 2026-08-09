---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:c1281066801d71cab642be52b1cebdb0b966e1a519c5d4bc71e1dfe8ed1e2cbf'
step_id: 'S09'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real CLI tests asserting the overview refusals name the field label and its legal basis and leave non-profile warning codes intact

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py`

## Description

- Added a fixture-anchor test asserting the gating field's operator label differs from its selector token, so the enrichment assertions cannot pass vacuously.
- Added enrichment tests against the real committed schema and the real registry authority: a profile selector token renders as its label, a non-profile warning code survives verbatim, and a mixed stream enriches only the profile entries while preserving order.
- Added CLI-level tests asserting the calendar refusal reads as a refusal rather than an invalid-value error, carries the remediation command, and that `--allow-incomplete` still renders.

## Outcome

The enrichment behaviour and the refusal channel are both covered by real-behaviour tests using the real schema, the real registry and the real CLI runner.

**One honest limit, stated because the first draft of this module asserted more than the fixture can support.** The initial tests assumed the calendar fixture's profile leaves the `has_employees` gating field unanswered, and parametrised all three verbs over a refusal. The run disproved both: the only warning that fires for that fixture is `censo.enrolment_unverified`, which is not a profile field at all, and the agenda and backlog verbs do not warn for that profile and exit zero. So the end-to-end path from an unanswered PROFILE field through a real CLI refusal to an enriched label is not covered here, and the agenda and backlog refusals are covered only by construction - they call the same builder on the same line shape as the calendar.

The tests were rewritten to assert what the fixture can actually demonstrate rather than adjusted until they passed: the enrichment function against real data, and the CLI refusal's channel and remediation. Notably the CLI test DOES exercise the pass-through branch end to end, since the code that reaches it really is a non-profile one. Closing the remaining gap needs a calendar fixture whose profile omits a gating field, which is a fixture this module does not have and which is recorded as follow-up rather than faked.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py -m integration -n 0 -q
    7 passed in 18.07s

Mutation probe, applied at runtime from outside the repository so no tracked file was modified, replacing the enrichment with a verbatim pass-through:

    MUTATION APPLIED: enrichment now passes every token through verbatim
    2 failed, 5 passed in 15.84s

The two failures were the label-rendering test and the mixed-stream test. The gate bites.

## Notes

The five failures on the first run were a wrong premise about the fixture, not a defect in the code under test. Recorded above rather than silently corrected, because the corrected module covers less than the original one claimed to.
