---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:67f01e5514f583a805e677478c2f82f545062e652fda409a469eb65264d5e6e0'
step_id: 'S54'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Re-check the create-mode already-enrolled refusal at install time, closing the window between the precondition check and the atomic install that stays open across an unbounded 24-word operator retype

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Extract the create-and-rotate enrollment precondition out of the enrollment
  entry point into a single named helper in `_recovery_facade.py`, so both
  refusal messages keep one authority and no string literal is duplicated.
- Call that helper a second time from inside the verify callback that gates the
  atomic install, placing the precondition on the same side of the operator
  confirmation pause as the write.
- Record the two-evaluation contract in the module invariant comment and in the
  create and rotate docstrings.
- Add a create-side regression that runs a complete competing enrollment from
  inside the confirmation callback, and a rotate-side regression that removes
  the envelope from inside it, in `tests/test_recovery_facade.py`.

## Outcome

The losing create now refuses. The mode precondition was previously read once,
before the operator was asked to transcribe and retype twenty-four words, and
never re-read; the install then wrote unconditionally, because the install
primitive sequences verify-before-write by design and deliberately asserts
nothing about the enrollment mode. An envelope enrolled by a concurrent
invocation during that unbounded pause was therefore silently replaced by the
create that the entry check had already decided to refuse, and the displaced
mnemonic became worthless.

The fix re-asserts the precondition inside the existing verify callback rather
than adding exclusive-create semantics. The callback is documented as the total
validation gate and is invoked immediately before the replace, so the check
composes with the established sequencing instead of introducing a second write
path. Exclusive-create was rejected because the hardened write is a temporary
file followed by a replace, and replace always overwrites; obtaining exclusive
semantics would have required a parallel write implementation that forfeits the
atomic-replace property, and rotate would still have needed the existing path,
leaving two write mechanisms inside one function.

A losing create raises the same typed refusal naming the rotate path that the
entry check raises, and the winning envelope is left byte-identical on disk and
still unwraps under its own mnemonic. The mode check runs before the mnemonic
verification so a refused write does not perform an unnecessary key unwrap. The
rotate precondition is strengthened rather than weakened: a rotation whose
envelope disappears during the pause now refuses instead of quietly completing
as a first enrollment. Mnemonic verification semantics are untouched.

Both regressions were confirmed to fail with the re-assertion removed and pass
with it present, and no other test in the module changed state, so the gate
detects the defect rather than restating the implementation.

## Notes

The install primitive was read but not modified; the fix is confined to the
facade and its tests.

Eleven tests in the persisted-session roundtrip module of the same package fail
in this environment with a Windows logon-session error on every keychain call.
That module is not touched by this change, the failures are confined to it, and
the cause is the known agent secure-shell session artefact rather than a defect;
it needs an operator console session to clear and is reported rather than worked
around.

Type checking was not run as a gate: the checker is configured in the project
manifest but the binary is absent from this environment and no task-runner
recipe invokes it. Lint and format checks are the live gates over these files
and both pass.

The mandatory code review was not dispatched from here, because this execution
context carries no delegation tool; it remains outstanding for the coordinator
to arrange, and this record should not be read as covering it.
