---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:aba6d7515a25d5b1db0561943c1439ee694aa3cdc01116c095af22d288b30fdc'
step_id: 'S01'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

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
