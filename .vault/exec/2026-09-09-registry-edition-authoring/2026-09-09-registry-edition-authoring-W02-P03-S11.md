---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:8e0af17386fd41c0afd7dc93713c3f107350c3736d8ef3bac702fe92a7ea8eb7'
step_id: 'S11'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Add the cache-teeth test: fingerprints follow the physical edition files read, never the expanded output. Proof: editing a delta file invalidates; a materialisation difference with identical files does not.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/tests/test_delta_edition_cache_fingerprint.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_delta_edition_cache_fingerprint.py src/cadrumo/domain/calculations/registry/tests/test_revision_edition_materialisation.py src/cadrumo/domain/calculations/registry/tests/test_mutable_tree_fingerprint_invalidation.py` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the added file -> `pass`

## Notes

- The tests drive `load_modelo_directory` and `load_registry_tree`, not `ValidatedRegistryAuthority.load`. At this HEAD the authority refuses any minimal temporary tree: it needs `categories/profiles.toml`, `iva/rates.toml`, `iva/recargo-rates.toml` and the full bundled global legal-parameter id set. The existing `test_authority.py::test_authority_cache_invalidates_when_fragmented_revision_changes` fails the same way (`CategoryValidationError`). `construct_authority` compiles through `load_registry_tree`, keyed on the same tree fingerprint the tests pin.
- Detector teeth were proven out of tree. A scratch pytest plugin, run in its own process, planted three defective collectors. Leaving out the predecessor edition's files failed 2 of 3 tests. Leaving out casilla fragments failed 3 of 3. Adding a row keyed on the expanded output failed 3 of 3. With no defect planted, 3 of 3 passed.
- No fingerprint defect found: predecessor and successor are editions of one modelo directory, and both collectors fingerprint every `revisions/**/*.toml`.
- Code review is still outstanding.
- The reviewer persona could not be launched. The orchestrating session reviewed the test against the ADR's physical-files cache constraint and re-ran it: 3 passed, ruff and ty clean, no mocks or monkeypatching.
