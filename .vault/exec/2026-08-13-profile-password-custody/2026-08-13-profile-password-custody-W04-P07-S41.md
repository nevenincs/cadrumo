---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7c0283e7207a7a2dc8fdda237f0a01d1fdbd3fb8ad9edae6ff78965918de7596'
step_id: 'S41'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore or remove the duplicate-label refusal that two live modules import from the profile facade but which is defined nowhere in the tree, an unrecorded casualty of the capsule discovery step that raises on import today

## Scope

- `src/cadrumo/application/user_profile/ and src/cadrumo/application/wizard/_commands.py`

## Description

- Restore the create-time duplicate-label refusal in `_resolve_profile_id_for_mode`, reading the committed-label projection the same function already consults one line later, and raising the wizard's registered validation error rather than a new class.
- Remove the registration guard on the non-create path as vestigial: the three lines beneath it resolve the same label and refuse when it does not resolve.
- Add the refusal's message to all four locale catalogues through the locale CLI, with real Spanish, Catalan and Hungarian text rather than a placeholder.
- Add an integration suite driving the real create door against real committed capsules, covering the mint, the refusal, its casefolding, the edit resolution and the unregistered-label refusal.

## Outcome

Two names were missing, and they did not have the same answer.

The duplicate-label refusal is real work and was restored. Without it `create` mints a fresh id for a label already bound to a committed capsule, the operator answers an entire flow against that id, and the collision surfaces only when the capsule cannot be published under a label already in use. The refusal is deliberately not a second authority: the race-free check remains in the custody service under the custody-root lock and still backstops this one. What was restored is the early, operator-facing refusal.

The registration guard was vestigial and was removed rather than reconstructed. It asserted exactly what the code immediately beneath it already established, so rebuilding it would have added a second reader of the same projection for no behaviour.

Neither missing name was reintroduced, and the surviving custody-service method was not promoted to fill the gap. That method is a publication-time guard keyed by profile id; lifting it to a pre-mint check would take the root lock a second time to answer a question it does not answer.

The refusal is proven to bite. Blinding the label lookup at runtime from outside the repository reproduces the defect state and reds exactly the three tests that observe the projection, while the unused-label mint and the unregistered-label refusal stay green — so the suite discriminates rather than passing on a blanket raise. Five tests, green in 14s. Lint and the `ty` type checker are clean on both touched files.

## Notes

The Step row framed this as one casualty with one decision. It was two casualties with opposite answers, and treating them alike in either direction would have been wrong: reconstructing both adds a redundant guard, removing both drops a real refusal.

The locale CLI was unavailable for much of this Step. Peer edits in flight left `domain/calculations/registry` importing names that did not exist, and the locale tooling loads the registry, so every attempt errored on an unrelated import until the peer's work settled. The four catalogue entries were set through the CLI once it ran, never by hand.

The locale parity and translation-resolution gates are currently red in this tree for reasons outside this Step: roughly four and a half thousand lines of uncommitted catalogue churn belonging to another agent, with about twenty-six unrelated `cli.help.*` keys missing. This Step's key was confirmed present, well-formed and carrying its interpolation placeholder in all four catalogues, and it appears in none of those failures.

The catalogues were therefore committed through an isolated index carrying HEAD plus this Step's four lines alone, and the staged diff was read back to confirm it contained nothing but the four translations. The shared index was then refreshed to HEAD for exactly those paths so a peer's bare commit could not revert this work, with the working tree proved byte-identical across the repair.

One shared-resource action to report. The index repair was blocked by a zero-byte `index.lock` that had not advanced in six minutes with no git process alive to own it. It was removed as crash residue, which also unblocked every other agent in the worktree; no process was stopped.
