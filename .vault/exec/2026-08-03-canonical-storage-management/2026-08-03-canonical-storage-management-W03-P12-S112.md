---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:2afa7e1cec0a2c5de419a36a0711f5a85a3753f64d6e0e992ba3c7c3d311232b'
step_id: 'S112'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Pin the two storage-kind enums where they overlap

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`
- `src/cadrumo/adapters/persistence/storage/_namespace_taxonomy.py`
- `src/cadrumo/tests/test_storage_kind_parity_gate.py`

## Description

- Verify the claim that this Step had already landed. It had not: no parity
  assertion existed anywhere in the tree, so the row was genuinely open despite
  a report to the contrary.
- Add `test_storage_kind_parity_gate.py` pinning the overlap between
  `StorageNodeKind` and `StoragePathKind`.
- Assert every shared member name carries an identical value on both sides.
- Pin the shared member set itself, so a rename on either side is caught rather
  than silently shrinking the intersection the value check quantifies over.
- Assert the adapter enum still carries members of its own, so the gate cannot
  red on legitimate growth and pressure a future author into merging the two.
- Add a positive control constructing a drifted spelling and proving the value
  comparison rejects it.
- Cross-reference the relationship in both enum docstrings, each stating why
  the two are not merged and which direction of change is dangerous.

## Outcome

The overlap is pinned and the divergence is preserved. `DIRECTORY` and `FILE`
must spell their values identically; `LOGICAL_SQL` and `BLOB_OBJECT` remain
adapter-only without disturbing the gate.

Mutation-proven rather than assumed. Changing `StorageNodeKind.FILE`'s value
from `file` to `single_file` reds the shared-member value check; restoring it
returns the suite to green. Five tests pass, and 41 pass across the gate, the
directory-agreement gate, the core taxonomy suite and the docstring-link gate.
Ruff clean on both edited modules.

The gate deliberately does not assert the member sets are equal. That stronger
assertion would red the moment the adapter declares a fifth kind, which is
exactly the growth the constraint-divergent finding exists to permit, and the
pressure it would create is to merge two enums that must stay apart.

## Notes

The Step asks for two things — a parity gate **and** a cross-reference in both
docstrings. The first landed alone in an earlier commit; the docstrings were
completed only when this record was written and the row re-read. A Step
satisfied in part reads as satisfied from the commit alone, which is the
argument for writing the record against the row rather than against the diff.

The row's reasoning was confirmed rather than assumed: `core` cannot import the
adapter type without inverting the layering, and a `StrEnum` already carrying
members cannot be extended to subclass another, so declaration is the only
available mechanism and convergence was never an option.

Both enums are `StrEnum`, so a member compares equal to its own string and
cross-boundary code relies on that. A divergent spelling therefore returns
`False` instead of raising — the failure is silent, which is what makes a gate
worth more here than a convention.

The scaffolder substituted this Step's heading and scope block *into* the
explanatory comment that describes those placeholders, duplicating both
mid-sentence and destroying the instruction. That is an upstream template
defect in `vaultspec-core vault add exec`, reproduced here and reported
elsewhere in the same campaign; the mangled comment blocks were removed by hand
when this body was authored.
