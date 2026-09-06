---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:f03c6a9b2c1370674c5a5bebd51bbcd09581d9fbfc7fa332b51c2cb76701f6a5'
step_id: 'S467'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hold the error spine assertion to the envelope model that declares it, since the hand-written member list named a suggestion field the model never carried and forbids, and split the text-mode case so the usage block is asserted on an input that raises a usage error rather than on a domain refusal

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_json_error_contract.py`

## Changes

All five `test_json_error_contract` failures are closed. 56 tests across the
error suites pass with no regression.

FOUR OF THE FIVE WERE ONE STALE LIST. `_assert_shared_spine` hand-wrote the
error members and included `suggestion`. `ErrorEnvelope` declares
`code, category, message, action, retryable, runbook_id, context, trace_id`
and sets `extra="forbid"`, so it has never carried a `suggestion` and could
not. `git log -S"suggestion: str"` on that module returns nothing: the field
was never there to be removed.

The contract deliberately does not have one. Free-text advice was replaced by
the typed `action` projection, and `_RESERVED_ACTION_CONTEXT_KEYS` in
`core.json_contract` reserves the word `suggestion` precisely so it cannot come
back through `context`. The test was asserting a member the design had gone out
of its way not to have.

IT WAS INVISIBLE UNTIL A SIBLING GAVE THE HELPER TEETH. Commit `17a6c9b59a`
("make four assertion helpers able to fail") swapped a lenient `_error_document`
for `require_error_document`; before that the loop never reached a real member
set. The failure this exposed is in the LIST, not in the code -- so the fix
reads `ErrorEnvelope.model_fields` instead, which is the authority for what an
error document carries, plus explicit assertions that `action` is declared and
`suggestion` is not.

THE FIFTH WAS AN INPUT THAT CANNOT PRODUCE WHAT WAS ASSERTED.
`test_text_mode_usage_error_keeps_human_rendering` demanded `Usage:` from
`app ledger view not-hex!`. A malformed transaction id is refused by the ledger
BOUNDARY, not by argument parsing, so no click `UsageError` is raised and there
is no usage block for anything to print.

Rather than drop the assertion, the case is split. The domain refusal now
asserts what it actually guards -- text mode stays text, and the refusal echoes
the operator's value with its structured facts -- and a new case asserts the
usage block on an unknown option, which genuinely raises a `UsageError`. That
rendering is exactly what S466 restored, so it earns an assertion of its own
rather than riding on an input that never produced it.

Teeth: two defects, each restored by copy. Restoring the S466 `view` typo fails
the new usage-block case; removing the `action` projection from `ErrorEnvelope`
fails four cases through the derived spine.

## Notes

I CHANGED TESTS RATHER THAN PRODUCTION CODE HERE, which needs its justification
stated rather than assumed. In both cases the authority was checked first: the
envelope MODEL declares the members and forbids extras, and the ledger boundary
-- not the parser -- is what refuses a malformed id. Neither assertion was
describing a behaviour the code had lost; each described one the code had never
had. The derived spine also removes the class of defect rather than the
instance, since the list can no longer drift from the model.

REMAINING PRE-EXISTING FAILURES, unchanged and not from this step:

* `test_parse_error_envelope_names_its_command` -- `config.profile` where
  `config.profile.preflight` is expected. Baselined as pre-existing in S466.
* three `test_audit` catalogue failures, whose values come from the concurrent
  TUI/sync commits.
* the two gates blocked on operator decisions: parity and the `direction`
  shadow.
