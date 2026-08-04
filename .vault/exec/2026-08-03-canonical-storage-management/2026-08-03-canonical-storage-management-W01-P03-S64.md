---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:6601d7d0a687c173ba8dc81c6928b490cae20587f24ac291eb12ec5e5440f4d0'
step_id: 'S64'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Delete the fifth unpinned buckets literal in the journal repository's containment check and read the taxonomy member instead, a copy found after the plan was authored and covered by no existing row, gated by the journal repository suite plus the name-unification gate seeing the module

## Scope

- `src/cadrumo/application/_journal_repository.py`

## Description

- Determined which kind of literal this is before touching it, per the R14
  discrimination: `_validate_existing_root`'s `buckets_root` is production
  safety code checking that the journal root does not nest under bucket
  storage, not a test measuring an accessor's correctness. If the taxonomy
  ever renamed the bucket container, the check must track the real location
  or its own guarantee silently rots -- the opposite of the sanctioned R14
  case (`test_every_derived_output_dir_roots_under_storage_root`), which
  must NOT route through the accessor because doing so would make it assert
  the accessor equals itself.
- Re-point `buckets_root` to `storage_location(StorageCategory.BUCKETS).
  relative_path()` joined onto `self._storage_root`, replacing the fifth
  hand-typed `"buckets"` literal.
- Confirmed byte-identical resolution (`Path("buckets")`).
- Extend the core name-unification gate (`test_storage_taxonomy_name_
  unification.py`) to cover `_journal_repository.py`, renaming its test
  function since the module set is no longer core-only, and documenting why
  an application-layer module belongs beside the core cases (plain drift,
  not the same hexagonal-direction constraint the other four cases share).
  Mutation-proven against a synthetic pre-fix snippet rather than by
  mutating the shared production file in place.

## Outcome

`JournalRepositoryBase._validate_existing_root` (shared by both the
config-reset and profile-export journal repositories) now reads the
bucket-container name once. Full storage/core/application suite re-run
clean: 1848 passed (one pre-existing, environment-dependent failure in
`test_config_reset.py` confirmed unrelated).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S25
in commit 8c94b7937b.
