---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:873f04ad4e0b47f0c6775d83b428001a8f66fd19d09dab8d9d3a58fc766523a3'
step_id: 'S239'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Add a central path-specific golden mask for only the profile-delete result fingerprint digest, retain generic digest visibility, and prove the mask is exactly the fresh-sandbox residual through real sequence replay

## Scope

- `src/cadrumo/core/observability/ and dev/docs/sequences/ and dev/docs/tests/test_sequence_goldens.py`

## Description

- Add a command-bound, exact-path golden mask for the destroyed profile fingerprint digest.
- Preserve generic digest and sibling fingerprint visibility through direct substrate tests.
- Execute the real documented logout/delete sequence twice in fresh sandboxes and pin its sole residual path.
- Prove file-count and byte-count tampering remains a comparison failure.
- Run focused observability, comparison, real replay, Ruff, ty, and independent formal review gates.

## Outcome

The central golden substrate now masks only `config.profile.delete` at
`result.fingerprint.digest`. The profile-delete sequence refreshes and checks
cleanly even though every fresh encrypted sandbox produces different destroyed
bytes, while every sibling field remains under exact comparison. Formal review
passed with no findings.

## Notes

The first unmasked refresh correctly exposed this digest as the only remaining
fresh-sandbox flap. No per-sequence mask parameter was added, and the committed
golden remains owned by the sequence refresh CLI.
