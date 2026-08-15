---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:b75016a13cc5e8ec944a22a9f0a0cc32d5bd1a0a4b2735d977b23b2932df0947'
step_id: 'S188'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the shared test seeding door record the empty retention snapshot that the production registration door records, since a seeded profile is otherwise indistinguishable from one whose filing owner was never asked and every deletion preflight against it refuses correctly for a reason unrelated to the test's subject, which is the fail-open shape the campaign closed in production reappearing in the surface every suite seeds through

## Scope

- `src/cadrumo/tests/user_profile.py`

## Description

- Record the empty filing catalogue snapshot at the shared seeding door through
  the recorder production registration already uses.
- Drop the local copy of that recording from the reset suite, which restored the
  fact one caller at a time.
- Prove a seeded profile is now deletion-assessable, and that absence still
  refuses.

## Outcome

**One added call, and the whole change is which door makes it.** The recorder is
the same function profile registration calls, invoked with the same empty record
set, so the seeding door now leaves a profile carrying the one fact registration
leaves it carrying. No second recorder was written and the snapshot was not
hand-constructed: the writer, its locking, its canonical path and its
best-effort swallow all stay in the one place that owns them.

**What it asserts is exactly true of a freshly seeded profile and nothing
more.** An empty recorded snapshot says the filing owner was asked and had
nothing to report. A profile that has just been published has filed nothing, so
that is a fact rather than a convenience. The stronger statement -- that no hold
of any kind blocks deletion -- is deliberately NOT made here, and the reason is
in the notes.

**The distinction it exists to protect is asserted in one test, not two.** A
seeded profile's deletion assessment now answers, and removing its recorded
snapshot makes the same assessment refuse again. Written as a pair in one test
because absence and recorded-emptiness converging is precisely the failure this
guards, and two separate tests would both stay green through it. The proof that
the assertion is load-bearing is a runtime plugin, from outside the repository,
that neuters the recorder at this door alone: the seeding test reds, and so does
the one other test in the suite that seeds through the same door and needs the
resulting profile to be assessable. The rest of the suite is unmoved, which is
what makes the reaction a signal rather than a blanket.

**The consumer set is fifty-nine modules besides the door itself**, spanning the authority suite,
modelo, ledger, review, filing, live capture, storage sync runs, user profile,
one domain suite, and the command-line surface including its shared conftest and
four support modules. The change is additive and cannot raise -- the recorder
swallows every failure by contract -- so the only reachable effect on any of
them is one more plaintext file under the custody hold directory, which the
storage taxonomy already declares because production registration writes it
there.

## Notes

**What was inherited versus verified.** The one-line delegation at the seeding
door, the reset suite's matching cleanup and this record's first draft were
authored before a session limit cut the step short, and a peer's broad sweep
commit captured the production half into the tree's history under an unrelated
subject. None of it was taken on trust afterwards: the door was re-read to
confirm it delegates to the production recorder rather than a second one and
records the empty set and nothing stronger, the consumer set was re-enumerated,
the ripple was measured over six suites, the load-bearingness was bite-proved
with a control the earlier pass could not obtain, and the predicted consumer
breakage was reproduced instead of assumed.

**The reset suite kept a local recording of a DIFFERENT fact, and that is the
honest half of this step.** The deletion preflight consults two hold owners.
The filing owner has a creation-time writer, which is what this row extends to
the seeding door. The legal case owner has none anywhere in production, so a
real registered profile carries no legal snapshot either and cannot be deleted
until something writes one. Recording it at the seeding door would have made
every seeded profile carry a fact no real profile has, turning a production gap
into a green suite. It stays in the reset suite's own helper, with the reason at
the site.

**One consumer is now wrong, it is confirmed wrong by measurement, and it is
not mine to correct.** The deletion assessment suite proves that absence refuses
by relying on the seeding door leaving no snapshot, which is exactly the
fail-open shape this row closes. Its absence half must now forge absence
explicitly -- delete the recorded snapshot, as this row's own test does --
rather than depend on the door's silence. The prediction was verified rather
than left as an inference: the recorded-empty-versus-absent test in that suite
now fails with a did-not-raise on the refusal it expects, which is the loud
failure and not a silent pass. That file belongs to another agent and is
reported rather than edited; it is one line, and it is the only regression this
row causes anywhere in the sample.

**The A/B comparison the earlier pass could not get was obtained, scoped
precisely.** The control is a runtime plugin that rebinds the recorder on the
filing package. The seeding door resolves it by a function-local import and
picks the rebinding up; the production registration door bound the same symbol
at module import and does not, so the control neuters the seeding door ALONE.
Under it the reset suite goes from five failures to seven: the seeded-profile
assessability test reds, and so does the read-only journal-view test that seeds
through the same door. Reverting the recording therefore reds exactly what
depends on it and nothing else, which is what makes the two green tests
evidence rather than decoration.

**The broad ripple sample is one thousand and forty-nine passing against
sixty-two failures and five hundred and thirty-three collection errors, and none
of the red is this row's but one.** Every error is the filing suite refusing to
publish a capsule for a non-UUID bucket id, from the change that made the
custody capsule the sole profile authority. The failures are the concurrent
registry-authority sweep, a stale caller passing the vestigial state argument
the seeding door stopped taking before this row, capsule directory anchoring
failures on this worktree's backing share, and review-suite identity-length
refusals. A recorder that never raises and writes one plaintext file cannot
produce any of those, and the one failure it CAN produce is named above.

**The recorder's own docstring now undercounts its callers and is not mine to
touch.** It says two callers write the snapshot, profile creation and filing
persistence. That remains true of production and is the claim that matters, but
the shared seeding door is now a third caller, and a reader auditing the
swallow-is-safe argument should know a test surface also exercises it.
