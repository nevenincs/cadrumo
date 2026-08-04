---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:57db4e35951872b588ca8a6cc3b7b228644c27a82238756ed040cd2539baa3ab'
step_id: 'S113'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S113 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Retire the _namespace_registry re-export bridge the path-hierarchy extraction left behind, re-pointing the five bucket modules that still import layout names from it onto _storage_path_definitions directly, and re-point the ten bucket and keystore taxonomy members' consumer_module claims at the modules that actually write the bytes rather than at the pass-through, since the liveness gate today is satisfied by an attribute load inside the bridge and verifies a weaker claim than its own docstring states and ## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_lockfile.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_manifest_io.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_output_language_hint.py`
- `src/cadrumo/core/_storage_taxonomy.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire the _namespace_registry re-export bridge the path-hierarchy extraction left behind, re-pointing the five bucket modules that still import layout names from it onto _storage_path_definitions directly, and re-point the ten bucket and keystore taxonomy members' consumer_module claims at the modules that actually write the bytes rather than at the pass-through, since the liveness gate today is satisfied by an attribute load inside the bridge and verifies a weaker claim than its own docstring states

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_lockfile.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_manifest_io.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_output_language_hint.py`
- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Verification only. Landed already at commit `5052c66641`, found while
  investigating this Step: `git log -1` on all five listed bucket/master-key
  modules pointed at that one commit before any edit of my own.
- Confirm no production module imports any of the thirteen layout-name
  constants from `_namespace_registry` anymore: a precise import-source scan
  (matching `from ... _namespace_registry import (...)`, filtered to the
  layout-constant names, excluding `_namespace_registry.py` itself) finds
  only one remaining hit, `StoragePathDefinition` in
  `test_namespace_registry.py` -- a legitimate use, since that symbol is
  genuinely constructed and re-exported by `_namespace_registry.py` itself,
  not part of the bridge concern.
- Confirm the ten bucket/keystore `consumer_module` claims in
  `core/_storage_taxonomy_locations.py` no longer name
  `_namespace_registry.py`.
- Re-run `test_storage_liveness_gate.py`, `test_storage_taxonomy_name_
  unification.py`, `test_namespace_registry_taxonomy_consumer.py`, and
  `test_namespace_registry.py`: 64 passed.

## Outcome

Already satisfied; no reimplementation performed. The landed commit went
further than this Step's own scope: it also caught and fixed a distinct
liveness-gate defect the bridge was suspected of propping up but did not
-- `StorageCategory.AUDIT`'s `consumer_module` claim was satisfied by an
unrelated `SensitivityClass.AUDIT` token collision in `_namespace_registry
.py`, referencing the storage category zero times. Re-pointed to the real
consumer (`application/live`, via `cadrumo_audit_dir`), mutation-proven by
aiming the claim at a module with no audit reference and confirming
`test_every_consumer_claim_is_backed_by_a_real_reference` reds.

## Notes

None. No skipped work, no scaffolds left in code. Not authored by me; recorded
here so the Step has an exec record rather than an inspected-but-unrecorded
gap.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
