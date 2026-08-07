---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:945d12667335dbb76409183740162bb7817d41d0eb7cc28963771714fee1a0b2'
step_id: 'S03'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
---

# Prove the new regression is load bearing by reverting the field to draft profile_tax_id, confirming the test reds, then restoring the fix

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0003-modelo-200-page-001b.toml`

## Description

- Run the new regression against the still-bound registry BEFORE the fix and capture the failure.
- Confirm the failure names the declarant's NIF in the emitted bytes.
- Apply the fix and confirm the same selection turns green.

## Outcome

The proof was taken from real tree state rather than by reverting the landed fix.
The regression was authored first and run against the registry as it then stood,
with the field still bound to the declarant's NIF. It failed on the emitted
bytes, showing the filer's 9-character CIF right-padded to 15 where AEAT expects
a foreign parent's identifier, with the first byte differing from a space.
Applying the fix turned the same selection green.

This ordering is strictly stronger than the reverting form the Step row
describes, and was chosen deliberately for two reasons. The red comes from the
tree as it actually shipped rather than from a state the proof constructed, so it
independently confirms the defect was live. And it never places a knowingly wrong
registry declaration in a shared worktree where many agents hold uncommitted work
and a peer's bare commit can sweep the tree at any moment, which is exactly what
happened during this execution, so a mutation window would have been swept into
the branch.

Both runs were serialised explicitly. The runner injects parallel workers through
addopts, and an in-session mutation never reaches those workers, so a proof run in
parallel can read green while proving nothing.

## Verification

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k grupo_mercantil_parent_tin -n0 -p no:randomly
    1 failed, 43 deselected in 24.66s          (before the fix)
    1 passed, 43 deselected in 55.35s          (after the fix)

The failure line read as an assertion that the 15-byte slice equalled fifteen
spaces, against an actual value of the declarant's identifier followed by six
spaces.

## Notes

No mutation window was opened, so nothing had to be restored and no wrong
declaration could be committed by a peer sweep.
