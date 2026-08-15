---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8dfb613a7a3fb3ee4062923632b3f5438af2585b0b0b8e74e4a0db2af84ee3c7'
step_id: 'S188'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S188 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have Terra XHigh make the shared test seeding door record the empty retention snapshot that the production registration door records, since a seeded profile is otherwise indistinguishable from one whose filing owner was never asked and every deletion preflight against it refuses correctly for a reason unrelated to the test's subject, which is the fail-open shape the campaign closed in production reappearing in the surface every suite seeds through and ## Scope

- `src/cadrumo/tests/user_profile.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
that neuters the recorder: the seeding test reds and its neighbour does not.

**The consumer set is fifty-eight test modules**, spanning the authority suite,
modelo, ledger, review, filing, live capture, storage sync runs, user profile,
one domain suite, and the command-line surface including its shared conftest and
four support modules. The change is additive and cannot raise -- the recorder
swallows every failure by contract -- so the only reachable effect on any of
them is one more plaintext file under the custody hold directory, which the
storage taxonomy already declares because production registration writes it
there.

## Notes

**The reset suite kept a local recording of a DIFFERENT fact, and that is the
honest half of this step.** The deletion preflight consults two hold owners.
The filing owner has a creation-time writer, which is what this row extends to
the seeding door. The legal case owner has none anywhere in production, so a
real registered profile carries no legal snapshot either and cannot be deleted
until something writes one. Recording it at the seeding door would have made
every seeded profile carry a fact no real profile has, turning a production gap
into a green suite. It stays in the reset suite's own helper, with the reason at
the site.

**One consumer is now wrong and it is not mine to correct.** The deletion
assessment suite proves that absence refuses by relying on the seeding door
leaving no snapshot, which is exactly the fail-open shape this row closes. Its
absence half must now forge absence explicitly -- delete the recorded snapshot,
as this row's own test does -- rather than depend on the door's silence. That
file belongs to another agent and is reported rather than edited; it is one line.

**The broad ripple sample could not be A/B compared, and the reason is worth
recording.** The sample ran once with the change; the control run, with the
recorder neutered, aborted at collection because a peer had added an error class
without its registry entry mid-flight, so it contributed zero tests. The
individual failures inspected in the sample name causes this change cannot
produce: a caller passing a positional argument the seeding door stopped taking
long before this row, a bucket opened before its capsule was published, and
registry validation errors from a concurrent registry sweep. A recorder that
never raises and writes one plaintext file cannot produce any of them.
