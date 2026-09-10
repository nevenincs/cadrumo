---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:a84188a44e99d5cb5f8410edd26ce659a333fa8e93b041fd558b1ffa7edba36d'
step_id: 'S55'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [S | sonnet-high] Make the materialiser's exclusion of non-casilla families explicit and tested, rather than relying on it merging only what it was told to. The completeness manifest is a revision section merged by the same fragment machinery as the casillas, so a materialiser written against the raw revision mapping picks it up by default; and its casilla collection is an append array whose duplicate-identifier validator would then refuse the load with an error naming a duplicate rather than naming inheritance. Loud but misattributed is still expensive. Proof: a planted delta whose predecessor has manifest rows materialises with the successor's own manifest untouched, and the duplicate-identifier path is never reached.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/tests/test_materialisation_excludes_non_casilla_families.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_materialisation_excludes_non_casilla_families.py src/cadrumo/domain/calculations/registry/tests/test_revision_edition_materialisation.py src/cadrumo/domain/calculations/registry/tests/test_loader_directory_fragments.py src/cadrumo/domain/calculations/registry/tests/test_completeness_manifest_authoring_shape.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_materialisation_excludes_non_casilla_families.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/domain/calculations/registry/tests/test_materialisation_excludes_non_casilla_families.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/domain/calculations/registry/tests/test_materialisation_excludes_non_casilla_families.py` -> `pass`

## Notes

- The reviewer persona could not be launched; the orchestrating session reviewed the test. Teeth for the manifest exclusion rest on the first test: a manifest-merging materialiser, run in a throwaway process, makes that load raise the duplicate-id refusal. The committed third test pins that refusal's text. Re-run: 3 passed, ruff and ty clean.
