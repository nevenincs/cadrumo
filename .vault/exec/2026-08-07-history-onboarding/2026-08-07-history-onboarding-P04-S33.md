---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0d3adcf0f6bf43848f752fcfc62c3eace2d6eeadbd2f7e342b8ca7cfb9fcb4ed'
step_id: 'S33'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# Enroll app live filed discover in the profile-bound write allowlist with a comment stating why a read-shaped verb writes: it persists nothing of the register it reads, which is why it is discover rather than pull, but it resolves its session through the central live-session writer, which opens an active-profile storage span and an auth mutation span. Its own docstring asserting that nothing is persisted is true of register data and false of session state, so enrolling on the docstring's word would be the error the census gate's own message warns against. Gate: the name-independent leaf census no longer reports the leaf as accounted for by no mechanism, and the MCP write-policy mutability parity gate still passes, since it requires every write-allowlist entry to map to a non-read-only family

## Scope

- `src/cadrumo/application/storage_write_policy.py`

## Description

- Trace the discover handler's session resolution rather than trusting its docstring.
- Confirm the central live-session bring-up opens an active-profile storage span and an auth mutation span.
- Confirm every sibling verb driving the same bring-up is already enrolled, including the read-shaped verify leaves.
- Add the allowlist entry with a comment stating why a read-shaped verb writes.
- Verify the overlapping MCP parity gate before trusting the fix, since it constrains the same allowlist from the opposite direction.
- Re-run the name-independent leaf census and confirm the leaf is no longer unaccounted.

## Outcome

The verb was reachable by NEITHER the profile-bound write guard nor the bootstrap exemption, so no storage-route refusal could apply to it. The guard failed open for it.

The handler's own docstring states that nothing is captured and nothing is persisted, and that is true of the register data it reads. It is false of the bucket: the verb resolves its session through the central live-session writer, which opens an active-profile storage span, refuses when no bucket resolves, and wraps the call in an auth mutation span. Enrolling the leaf in the reviewed-non-mutating roster on the strength of that docstring would have been exactly the failure the census gate's own message warns against, since that roster asserts the write path was traced and none found rather than that the name reads like a query.

The classification is also consistent with every sibling: each verb driving the same bring-up is already enrolled, including the read-shaped verify leaves, which write only an audit observation. So the enrolment restores a pattern rather than inventing one.

A deeper question is deliberately NOT settled here: whether a discovery verb should drive the session writer at all, or whether the session bring-up should be split so a read can resolve a session without a bucket write. Enrolling the verb records what the code does today; changing what it does is a design decision outside this row, and it is left open rather than silently resolved by the enrolment.

## Verification

The leaf census, before:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py -n0 -q -m integration -vv
    AssertionError: `app` leaf/leaves accounted for by NO mechanism: ['app ledger counterparty confirm', 'app ledger counterparty withdraw', 'app ledger evidence batch', 'app ledger evidence consent list', 'app ledger evidence consent rederive', 'app ledger evidence review list', 'app ledger evidence review show', 'app live filed discover']

After:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py -n0 -q -m integration
    2 failed, 18 passed in 132.64s (0:02:12)
    AssertionError: `app` leaf/leaves accounted for by NO mechanism: ['app ledger counterparty confirm', 'app ledger counterparty withdraw', 'app ledger evidence batch', 'app ledger evidence consent list', 'app ledger evidence consent rederive', 'app ledger evidence review list', 'app ledger evidence review show']

The target leaf is absent from the second list, and the remaining seven are ledger leaves belonging to other campaigns. The gate stays red on those, which is owner triage rather than this row's failure.

The overlapping gate was checked BEFORE trusting the fix, because this repository's gates constrain the same allowlist from opposite directions and satisfying one can violate the other. The MCP write-policy mutability parity gate requires every write-allowlist entry to map to a command whose family is not read-only:

    command_classification("live.filed.discover").read_only
    False

So both gates agree and there is no oscillation between them.

## Notes

The edit was swept into the published history by a peer's bare whole-index commit before it could be committed under its own message, so the change is carried by a commit whose subject describes unrelated in-flight work. The explanatory comment survived intact in the file content, so the rationale is not lost, but the commit history does not attribute it. Recorded here because the record is the only place that attribution now exists.

A second failure in the same gate is peer-owned and needs an owner: one ledger leaf is a MUTATING leaf reachable by neither the write guard nor the bootstrap exemption, so it currently fails open the same way this verb did. It is named in the verification output above. Not fixed here, because it belongs to an active ledger campaign and patching another campaign's surface to green a gate is the move this project forbids.

The unaccounted count grew from six to eight across two runs minutes apart, so those leaves are actively landing. Any later reading of this gate should re-measure rather than trust the counts recorded here.
