---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:56f5629f5169983b34fb2c2ab348a85a9b963785ceaf9f19fb9eedb88b8872eb'
step_id: 'S17'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Delete the untyped derived-dirs dict and the transitional parity test in one commit, gated by clean collection over the whole source tree immediately before the commit

## Scope

- `src/cadrumo/core/config.py`

## Description

- Delete the untyped derived-dirs dict and the transitional parity test in one commit, gated by clean collection over the whole source tree immediately before the commit.

## Outcome

Landed in commit `86b02bf68e` ("anchor the keystore at the storage root, not under buckets/"), the same commit as the keystore-scope fix (S79). Its commit message states the deletion rationale directly: "Deletes `_STATE_ROOT_DERIVED_DIRS` from `core/config.py`: zero remaining consumers now that `core._storage_taxonomy` is the sole authority and `test_output_dir_state_root.py::DERIVED_OUTPUT_SUBPATHS` is the independent [oracle]." Verified independently at committed HEAD, not taken from the commit message alone: `git show HEAD:src/cadrumo/core/config.py | grep _STATE_ROOT_DERIVED_DIRS` returns nothing, and `git show HEAD:src/cadrumo/core/tests/test_storage_taxonomy_parity.py` fails (the file no longer exists). Both halves of this Step are confirmed done.

## Notes

R20's blocking coupling (the peer-owned lifecycle gate importing this dict in five places) was resolved earlier when that gate was rewritten (`88c9faac4e`), which unblocked but did not itself perform this deletion. The physical deletion landed separately, bundled into the unrelated keystore-scope fix commit rather than its own. Caught by independent re-verification of the ADR's R20 claim rather than assumed from the earlier "unblocked, not yet executed" state — the coordinator asked for this Step to be verified against HEAD directly rather than taken on report, and it was.
