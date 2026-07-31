---
tags:
  - '#exec'
  - '#profile-bundle-tui'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:852ccc1c564cb8f4803d939aeae3834f5f5da954c9a909ade344385fce459d34'
step_id: 'S05'
related:
  - "[[2026-07-25-profile-bundle-tui-plan]]"
---

# Keep passphrase collection on the pre-existing hidden confirm-retype prompts after the flow exits rather than moving secret entry into the flow, and prove a console-less host cannot reach an echoing fallback

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`

## Description

- Keep the passphrase off every flow page, leaving the shared secure-input channel as the single passphrase authority, so no secret ever lands in a flow answer map or a review projection.
- Collect the passphrase only after the flow exits, on the pre-existing hidden confirm-retype prompts, unchanged for interactive and fully-specified invocations alike.
- Keep the strict bounded stdin payload as the scripted alternative, so the passphrase is never an argv value on any path.
- Declare checkpointing UNAVAILABLE on both definitions so nothing collected can be written to disk mid-run.

## Outcome

Landed in commit `c4545973f9`, over the secure-input guards from `368d702047` and `2de49004db`. This pass verified the step rather than re-implementing it.

The structural half is pinned by `test_neither_definition_carries_a_secret_page_or_checkpointing`, which asserts no SECRET widget appears on either definition and that both declare checkpointing UNAVAILABLE in every mode.

The console-less half is proven, not asserted. `uv run --no-sync pytest src/cadrumo/entrypoints/cli/_config/tests/test_secure_input_echo_guard.py -m integration` passes all six proofs, each driving a real interpreter subprocess with nothing patched. It carries its own anti-tautology anchor: one probe first proves the stdlib echoing fallback is genuinely reachable in this interpreter and really returns the planted secret, so the refusal proofs cannot pass vacuously. The console-less case is constructed for real as a detached-process spawn and the test fails on timeout, so a regression that re-introduces the block cannot pass by hanging. A separate probe isolates the echo-suppression guard on a genuine console with rebound stdin — the one channel where that guard is the deciding check — and confirms the refusal fires before any character is read.

The guard does not rely on an exception hierarchy that would let a Windows operator through. It fails closed on a real-console probe ahead of the prompt, and promotes the stdlib's echo warning to an exception at the point the fallback emits it, so every fallback route is covered rather than only the ones an exception filter anticipates. A redirected-pipe probe additionally asserts the planted secret never reaches stdout or stderr.

## Notes

All six proofs passed on this host, including the real-console case, so no console-only remainder is outstanding for this step.
