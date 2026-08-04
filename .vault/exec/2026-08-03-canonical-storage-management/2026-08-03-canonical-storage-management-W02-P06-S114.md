---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:618b5b2b03e5b86bc1159bc40b11184e43cdf7ea1ed2df9da1837a416b77e8fd'
step_id: 'S114'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Interpolate the fourteen STORAGE_PATH_DEFINITIONS grammars' hand-typed directory-run literals off storage_location(StorageCategory.X).subpath the same way the adjacent segment field on the same model already does, retiring the directory-agreement gate by construction rather than leaving it green by comparison, optional and lower priority than the anchor and namespace-segment fixes since the gate does hold today for the sixteen storage-root-anchored entries, but real duplication under the campaign's own no-duplication standard

## Scope

- `src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py`

## Description

- Read the table at HEAD first, since a peer's anchor-field work (`S111`)
  touched the same declarations. Confirmed the `anchor` field additions did
  not change the fourteen entries this Step targets.
- Identify the fourteen `StoragePathDefinition` entries that already declare
  a `segment=` field derived from `storage_location(StorageCategory.X).subpath`
  (twelve) or a plain local constant (`secret_index`, `config_reset_journal`
  -- the latter blocked on `S25`, which has not landed, so its constant stays
  a plain literal rather than a taxonomy read).
- Add `ROOT_FALLBACK_DATABASE_FILENAME` as a module-level constant, matching
  the pattern the other twelve already use, so `root_fallback_database`'s
  `segment=` and `grammar=` read the same single call site.
- Rewrite each of the fourteen `grammar=` strings as an f-string
  interpolating the identical constant its `segment=` field already reads,
  removing the second hand-typed occurrence of the same literal.
- Confirm every one of the 29 declared grammars renders byte-identical
  before and after the change.
- Leave every entry with no `segment=` field untouched (the nested
  `bucket_database_file` and the parameterised fan-out shapes) -- there is
  no adjacent constant for them to interpolate from, so they are out of this
  Step's stated scope.

## Outcome

Fourteen real duplications removed: each of these entries previously spelled
its directory-run or filename literal twice within the same module (once in
`segment=`, once hand-retyped inside `grammar=`); now both read the one
declared constant. The directory-agreement gate held green before and after
this change either way -- it compares the resolved live path, not the two
spellings inside one declaration against each other, so this closes a
duplication the gate could not see rather than a defect it was already
catching. Full storage/persistence suite plus the taxonomy suite re-run
clean: 1216 passed. Full-tree collection (19000 tests) confirmed no import
regression.

## Notes

None. No skipped work, no scaffolds left in code. Left `bucket_database_file`
and the ten fan-out/nested entries untouched by design (no segment field to
interpolate from), consistent with the Step's own "fourteen" scoping.
