---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:67fd3e2bcccddecc821e5f8793d71300a9d2bb0fbc93c19dba2dfb128edd2c4a'
step_id: 'S11'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Build the registry selector parity gate binding declared period_selector tokens to the accepted set, delegating to the production validator rather than restating it so the gate cannot become a second authority

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Bind every `period_selector` token declared in shipped registry TOML to the accepted period vocabulary.
- Validate through `TypeAdapter(RegistrySelectorPeriodCode)` and enumerate through `accepted_period_codes()`, so the gate names no token family itself.
- Add three planted-violation arms, each asserting the clean corpus is clean and the violation is reported.
- Pin the measured corpus so a discovery that stops matching reds rather than passes.

## Outcome

Landed as commit `9201f562ab` ("test(registry): bind registry selector tokens to the
accepted period vocabulary"), one file, 194 insertions and 0 deletions. The sha was
resolved with `git log --format=%H --grep=` and read with `git show <sha> --numstat` per
the plan's commit-verification rule, never with `git show HEAD`.

The row's binding constraint was that the gate delegate to the production validator rather
than restate it, so it cannot become a second authority. The landed gate satisfies that
structurally rather than by discipline: it validates through a `TypeAdapter` over
`RegistrySelectorPeriodCode` and enumerates through `accepted_period_codes()`, and
therefore nowhere names which token families are accepted. A widening of the production
validator propagates into the gate on the next run instead of leaving the gate asserting a
stale set, which is the drift a hand-restated set would have introduced.

## Notes

The row's closure criterion is stricter than a passing test: it closes only when the gate is
shown to FAIL against a planted violation, because a parity gate whose discovery silently
finds nothing is indistinguishable from one that passes on a clean tree. Three arms plant a
violation and assert it is reported — an injected token the validator refuses, a declared
token removed so its accepted code surfaces as undeclared, and an upper-case administrative
spelling that validates but is stored differently from how the TOML spells it. Each first
asserts the unpoisoned corpus is clean, so the arm cannot pass by finding a pre-existing
violation.

Executed both this gate and the coverage pin of `S18` in one invocation: 15 passed. The
first attempt reported `NOTHING RAN` with all 15 collected tests deselected by the default
lane's marker expression; the integration marker is required. That is worth recording
rather than quietly re-running, because a green default-lane result here would have been a
selection matching nothing — the same false-green family as the silently-empty discovery
the planted-violation arms exist to rule out. The row was verified in the lane that
actually selects it.

Measured the pinned corpus independently of the gate's own assertions: 90 revisions
declaring a selector and 31 distinct selector tokens, against pins of more than 80 and more
than 25. Both pins have real headroom and neither is vacuous.

A figure correction belongs here. An earlier report of this work cited 91 revisions; the
value is 90. The first was a file count and the second the compiled value, and the gate
pins the compiled one. That distinction is the same one the registry fragmentation rule
draws — a revision's content is what the loader compiles, not what a directory listing
suggests — so a gate pinned to a file count would have drifted from the corpus it claims
to measure.

A third check was added beyond the row's specification and disclosed rather than absorbed.
The row asked for declared-token-to-accepted-set parity; the landed gate also checks
canonical declaration form. That catches a real gap, because the selector lowercases
administrative tokens, so an upper-case TOML declaration is accepted and then stored unequal
to its source spelling. The addition was accepted on review.

One measurement note for a future reader. The independent corpus measurement raced a
concurrent registry write on its first attempt and refused with `registry directory changed
during cache fingerprinting`. That is the loader behaving correctly under peer activity in a
shared worktree, not corpus instability; the retry succeeded.
