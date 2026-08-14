---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:2820c3c0cc54d50492c579bda80fe92c45f1b279de283ed0f322f9b187af0aa7'
step_id: 'S102'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Delete the production re-export bridge the import-hygiene gate reports and repoint its consumers

## Scope

- `src/cadrumo/adapters/persistence/storage/custody`
- `src/cadrumo/core/_storage_taxonomy_locations.py`
- `src/cadrumo/tests`

## Description

- Confirm the shipped gate is red on the bridge before changing anything.
- Repoint the package facade at the two real defining modules and delete the bridge.
- Sweep every importer, including the storage-liveness taxonomy's consumer claim.
- Delete an orphaned test adapter module whose only consumer had already been removed.

## Outcome

The package facade imports from the modules that define the symbols, and the intermediate file holding only imports is gone. The gate that had been failing passes, and the tree's declared position of zero production re-export bridges is true again rather than merely asserted.

The deletion had a second consumer the obvious search does not surface. The storage-liveness taxonomy named the bridge as the consumer module for a storage category, and a separate gate checks that the named module both exists and genuinely references that category. The bridge never referenced anything, being pure re-export, so the claim now names the repository module that actually reads it.

A second module went with it for a different reason. A test adapter existed solely to give one large test module a single import point for real adapters; that test was deleted earlier the same day and the adapter module was left behind with no importer anywhere. That is a deletion-completeness gap rather than a bridge question, and it was invisible because the bridge scan does not look at the test tree at all.

## Notes

The tempting repair was to add the path to the baseline the gate compares against. That baseline is the tree's declaration that no production bridge exists, so an entry would have converted a real defect into a blessed one, which is precisely what the gate exists to prevent. The bridge was deleted instead.

The surrounding package was under heavy concurrent edit throughout, so only the three files this change owns were committed and the neighbouring in-flight work was left alone.
