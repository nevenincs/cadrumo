---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:99012aa2413ab3000c5322c0b84aea09d1699a51fdf817053281be5b68a5b65b'
step_id: 'S154'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh wire the filing retention assessment into the deletion preflight, since the contract is now fully answerable but the producer still refuses every existing target for want of an authenticated retention assessment, which is the sole cause of fifteen failing reset recovery and concurrency modules

## Scope

- `src/cadrumo/application/bucket_maintenance/_service.py`
- `src/cadrumo/application/bucket_maintenance/tests/test_service_assess_deletion.py`
- `src/cadrumo/application/profile_custody/__init__.py`
- `src/cadrumo/application/tests/test_config_reset.py`
- `src/cadrumo/application/tests/test_config_reset_concurrency.py`

## Description

- Reproduce the unconditional refusal against a real published capsule before changing anything.
- Consume the filing owner's retention assessment and the custody capsule inventory in the preflight.
- Separate the three snapshot states so absence and recorded-emptiness cannot converge.
- Re-found the concurrency exclusion harness on a writer that still exists.

## Outcome

**The refusal was unconditional, and reproducing it is what makes the rest
honest.** The producer resolved the target's paths, confirmed it had a
committed label projection, and then raised regardless of any fact it had just
established. Nothing was consulted; the raise was the terminal statement of the
method, so every existing target refused and no argument could change that. The
reproduction against a real capsule in an isolated root confirmed both halves in
one run: the existing target raised, and the absent target still answered
correctly, which localised the defect to the existing branch alone.

**This was a wiring step, and the discipline was to keep it one.** Every input
already existed: the filing owner's assessment returns the whole retention
position rather than a flag, the custody adapter already inventories a committed
capsule, and the assessment contract already carried optional retention and
fingerprint fields whose validator demanded them for an existing target. No
producer was written, no second retention path was created, and the floor is
still computed in exactly one place. The preflight now reads the assessment the
filing owner publishes and folds the inventory the custody adapter observes.

**Three snapshot states, three behaviours, and only one of them permits an
erase.** A recorded snapshot listing no filings is an answer and clears the
retention axis. An absent snapshot means nobody was ever asked, and it refuses.
A snapshot present but unparseable or unauthenticated is the same non-answer
with a different cause, and refuses separately. The two refusals carry different
structured context because they have different remedies, and a message that said
only that a retention assessment was required is what an operator had before.

**The refusals name the concrete gap.** Each states what could not be assessed,
why the unknown is not a clearance, and what would produce the missing fact --
that the snapshot is written at profile creation and refreshed on every filing.
The fingerprint has its own refusal for the same reason: a substituted value
would blind the resume-time change detector rather than fail it.

**Bite-proved in both directions, from outside the repository.** Two runtime
plugins on the interpreter path, no tracked file touched, so a peer's sweep
could not capture the mutation. Degrading an absent snapshot into an empty
assessment fails the absence test and leaves the other four green. Forcing the
floor to retain nothing fails the floor test and leaves the absence test green.
That pairing is the whole point: a guard that refuses everything is exactly as
broken as one that refuses nothing, and refusing everything was the actual
defect.

## Notes

**The next wall in this chain is not retention, and it is already ruled.** With
the preflight answering, every remaining reset failure is the same one: clearing
operator auth for a target calls a revocation that refuses without a custody
session for that bucket. That refusal is not a defect -- an earlier step in this
campaign ruled it deliberately, because the session being revoked is an
encrypted row inside the bucket and deleting it genuinely needs the key. A reset
holds locks on targets it has not unlocked, so the auth phase is structurally
unreachable in exactly the way the retention phase was before this step. It
needs its own ruling, most plausibly that in-bucket auth rows die with the
capsule and only the key-free artefacts outside it need explicit clearing. It
was not decided here.

**The seeding door and the registration door leave different profiles, and that
is a wider finding than this step.** The empty snapshot is recorded by profile
registration; the test seeding door publishes a capsule directly and records
nothing. Every seeded profile therefore looks like one nobody asked about its
filings, and any deletion preflight against it refuses correctly for a reason
unrelated to the test's subject. The reset tests now restore that one fact
through the same recorder registration calls, which is what the sibling custody
helper in the same module already did. Fixing it at the shared seeding door
would serve every suite, and was left alone because that door is not this step's
to change.

**The concurrency exclusion harness was driving a verb that no longer exists,
and the retention refusal had been hiding it.** The harness proved a real
application writer is locked out of a reset-owned bucket by attempting a bucket
rename; bucket maintenance became read-only and the rename went with it, so the
harness failed on import. The surviving label mutation takes the custody lock
rather than the per-bucket lockfile, so it could not prove this exclusion at
all. Auth revocation was chosen instead because it is the writer that still
enters a named bucket through the same per-bucket lockfile a reset holds, so the
exclusion asserted is a real cross-surface one and not a lock the reset shares
with itself. Its session is opened first, deliberately: without one the
revocation refuses outright and would satisfy the busy assertion for the wrong
reason.

**The inventory reached past the application boundary on the first attempt.**
The preflight imported the custody persistence adapter directly, which the
layered-architecture contract forbids and which the import linter caught as a
newly added edge. It now goes through the application-owned custody port, which
is the package that exists for exactly this and already imports that adapter
legitimately. The dependency count fell by exactly one against the prior run and
the preflight no longer appears among the contract's violations.

**Attribution of what did not go green.** In the six suites this step owns the
count moved from twenty-one failing to eighteen, with five new tests added and
passing. Seventeen of the eighteen are the auth revocation wall above; the
remaining one is a Windows file-in-use error on a bucket database, which is the
backing share this worktree is known to fail on. The retention refusal appears
nowhere in the run. A wider run also swept the filing suite, which showed
hundreds of registry validation failures from a concurrent registry rewrite;
none of that is claimed or absorbed here, and the two filing retention modules
this step consumes both passed inside it. The import hygiene gate is red on
sites that predate this step and name none of its files.

**A peer's broad commit captured this work mid-step.** No commit was made from
this step, and the changes were found already in the tree's history under an
unrelated sweep subject. The content is intact; the attribution is not, and it
is recorded here because that commit message says nothing about retention.
