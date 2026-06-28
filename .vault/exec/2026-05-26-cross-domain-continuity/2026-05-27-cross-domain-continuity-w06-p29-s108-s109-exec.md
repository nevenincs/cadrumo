---
step_id: S108
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-cross-domain-continuity-w06-p28-s104-s107-exec]]"
---

# cross-domain-continuity W06.P29.S108-S109 — import idempotency + regression test

## Outcome

S108 satisfied by existing S106 implementation (D5 two-tier collision guard
already in `config_profile_import`). S109 new test file committed at
`e5a7979a5`. Plan steps S108-S109 closed. 3/3 new tests pass.

## S108 — Idempotency mode (satisfied by S106)

The idempotency contract was already implemented as part of S106:

- Bundle's `profile_id` UUID is preserved on import (ADR D5; `_atomic_create_profile`
  accepts optional `profile_id`).
- Tier-1 UUID collision guard: `read_profile_bucket_by_id(bundle_profile_id) is not None`
  → refuses with "profile already registered".
- Tier-2 label collision guard: `read_profile_bucket(target_label)` taken by a
  different UUID → refuses with "label taken, use --label".

No code changes required for S108. Step plan-closed against existing
`af81954a6` implementation.

## S109 — Idempotency regression test

New file `src/aeat/entrypoints/cli/test_profile_import_idempotency.py`
(222 lines, commit `e5a7979a5`):

- `test_reimport_same_bundle_is_refused`: creates a minimal profile, exports
  it, imports once (succeeds), imports again (refused with "already registered");
  `profile list` and `profile show` confirm exactly one profile with the
  correct UUID.

- `test_label_collision_different_uuid_refused_even_with_explicit_label`:
  a locally-minted profile occupies the label; importing the bundle both
  without and with `--label <same>` is refused; `--label <free>` succeeds.

- `test_mutated_profile_id_creates_second_profile` (anti-tautology):
  UUID-mutated clone of the bundle is imported under a distinct label.
  Both profiles exist; `profile show` for each label returns the matching
  UUID, proving UUID is the genuine discriminator.

`isolated_profile_storage_root` fixture throughout; no mocks; real
encrypted repositories.

## Files changed

- `src/aeat/entrypoints/cli/test_profile_import_idempotency.py` (NEW, 222 lines)
