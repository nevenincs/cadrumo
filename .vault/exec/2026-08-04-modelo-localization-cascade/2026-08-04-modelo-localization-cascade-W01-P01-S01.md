---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:32ebeb9523f554975fd56139f283149de2269d4e65a766b671dcafa008d3c54f'
step_id: 'S01'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-localization-cascade with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Pin the corpus fingerprint and supported revision inventory and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Pin the corpus fingerprint and supported revision inventory

## Scope

- `dev/registry/migration`

## Description

- Add the read-only `dev/registry/migration` source-contract package.
- Fingerprint every registry TOML by canonical relative path, byte count, and SHA-256 content hash.
- Load supported Modelo and revision identities through the public registry loader and source descriptors.
- Enforce strict immutable records, source-drift refusal, deterministic ordering, and JSON round-trip integrity.
- Add real bundled-tree and temporary-filesystem tests for repeatability, tamper refusal, and no source mutation.

## Outcome

- Modified files: `dev/registry/migration/__init__.py`, `dev/registry/migration/manager.py`, `dev/registry/migration/tests/__init__.py`, and `dev/registry/migration/tests/test_source_inventory.py`.
- The bundled source census is 16,519 TOML files (24,849,174 bytes), including 281 locale files, with corpus SHA-256 `0798a5518e615ee7d52e251f581f2522219ee83fe7d4561b89bd89d1cc9e025e`.
- The canonical loader supports 73 Modelos and 90 revisions; each inventory row records its Modelo/revision source paths and layout without reading or emitting migration leaves.
- The inventory is content-addressed and machine-independent, while the pre/post read fingerprints reject a mixed snapshot if the source tree changes during collection.

## Notes

- Focused validation passed: `uv run --no-sync ruff check dev/registry/migration`, `uv run --no-sync ruff format --check dev/registry/migration`, and `uv run --no-sync pytest dev/registry/migration/tests/test_source_inventory.py -q -n 0 -m integration` (`4 passed`).
- An initial test exposed Windows filesystem ordering differing from canonical POSIX path ordering; the sort key was corrected before the green run.
- This step intentionally stops before resolved localization extraction, classification, emission, dry-run artifact writing, parity, or production mutation.
