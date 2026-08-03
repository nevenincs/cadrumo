---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:49200e0eb7d56b1dcfaea0a8accf2bf5dc18c9563ff88b5cfe4427785baf2f28'
step_id: 'S86'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Decide whether the blob-store's sha256-prefix fan-out is a governance gap or a correctly-excluded data-derived segment, since the hash prefix is a content digest rather than an application choice, the same reasoning the audit applied to exclude a run_id from R5's scope, and if excluded record the exclusion explicitly rather than leaving it silent and indistinguishable from an oversight

## Scope

- `src/cadrumo/adapters/persistence/storage/blob_store/_blob_store.py`
- `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py`

## Description

- Decide whether the blob-store's sha256-prefix fan-out is a governance gap or a correctly-treated data-derived shape.

## Outcome

Already governed, not excluded — a distinct third disposition this Step's own text didn't anticipate. Landed in commit `3a6ce7475d` ("extract the filesystem path-hierarchy contracts into a sibling module"), which adds `StoragePathDefinition` and `STORAGE_PATH_DEFINITIONS` in the new `_storage_path_definitions.py`, explicitly for "parameterised fan-out shapes (a content-hash prefix, an outbound namespace, a per-run id) that cannot be enumerable `StorageCategory` members." `blob_content_plaintext` (`grammar="<root>/blobs/<sha256[:2]>/<sha256>"`) and `blob_content_ciphertext` (`.enc` suffix) declare the shape with a placeholder for the data-derived hash segment. Gated by `blob_store/tests/test_blob_content_shape_conformance.py`, which drives a real write through the real production path and asserts the real resulting path matches a regex derived from the grammar — not the grammar compared against itself.

## Notes

The distinction this Step surfaced: a data-derived segment (a content digest, a run id) is not "excluded" from governance — it is governed by grammar rather than by taxonomy membership. Declaring it as a `StorageCategory` member would be a category error (you cannot enumerate members per hash); the grammar mechanism expresses the shape instead. My first pass at this Step framed it as needing an exclusion statement, which was wrong — the mechanism already existed and a peer lane had already used it, corrected on review before I could act on the wrong framing.
