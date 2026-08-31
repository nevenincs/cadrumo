---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:268e51a0452074e658edafa546b1fc3ccf02fba2ff9f71212b32dd59a503c1a8'
step_id: 'S347'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make the recovery-handoff confirmation survive a loaded machine, where it currently fails non-deterministically: two parametrised cases fail under concurrent load and pass in isolation, and the evidence that this is a race rather than a defect in either case is that THE FAILING PARAMETRISATION MOVES BETWEEN RUNS -- a deterministic fault does not migrate. The mechanism is that the handoff blocks a worker thread on a bounded event while a real key derivation runs, and the bound is sized for a machine doing nothing else. DO NOT lengthen the bound or the pause to make it green: that converts a race into a slower race and hides it behind a number that will be wrong again on the next slower machine. The tests have already been hardened to wait on the real postcondition rather than a bare pause and they still fail under load, so the waiting is not the problem -- the bound is. Establish what the handoff is actually waiting for and bound the wait by that condition rather than by elapsed time, or make the derivation's completion observable so the handoff can wait on it directly. Prove it under genuine concurrent load, since an idle run passes against the defect

## Scope

- `the recovery-handoff confirmation's bounded wait`
- `the key-derivation completion signal it depends on`
- `and a proof run under concurrent load`

## Changes

- `M` `src/cadrumo/entrypoints/tui/secret/registration.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_registration_recovery_words.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_registration_recovery_words.py -m integration` -> `pass`

## Notes

The wait was never measuring elapsed time. Its own comment said the thirty-second
bound was a final guard for a failed message-loop lifecycle, and the event has
exactly three releasers: the operator confirms, the operator cancels, or
`on_unmount` releases every pending handoff at shutdown. The genuine failure is a
message loop that stopped without releasing, which is a liveness condition. The wait
now polls the event and gives up only once the app is no longer running.

The bound was also wrong independently of the race it caused: thirty seconds is a
deadline on a human copying down a twenty-four word recovery mnemonic, and
overrunning it discarded the enrollment silently. An operator taking their time is
not a failure.

The proof waits thirty-three seconds before confirming, deliberately past the removed
bound, because a shorter delay passes against the defect and proves nothing. This was
chosen over the concurrent-load reproduction the Step suggested: a load run passes on
an idle machine, which is why the original failure moved between runs, whereas this
fails deterministically against the old code on any machine.

Gate proven by mutation: restoring the pre-fix `_confirm_recovery_possession` from
outside the repository reds the new proof and also reds
`test_the_full_screen_door_shows_the_words_then_wipes_them`, a pre-existing test
exercising a prompt confirmation with no operator hesitation at all. Two failed and
three passed under the restored defect, against five passed on the fix. That second
failure is the corroboration: the mutation reproduced the reported load-dependent
symptom on a test this Step did not author.

The production half of this change reached main inside an unrelated peer commit whose
subject names a review-package relocation, and the proof test reached main in a later
one. Neither commit subject records that this defect was fixed.
