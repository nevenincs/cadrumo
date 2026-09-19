---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c6db4fdd214522ac221929b1e582e55b122e29745abd2b89ac5f1cf38e6e5b97'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-semantic-map-fragment-loader-reference]]"
---
# `aeat-export-fragment-generator-authority` audit: `s42 semantic map fragment loader`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

This independent review covered approved plan step `W04.P07.S42`, the accepted generator-authority ADR, the semantic-map fragment-loader reference, and the complete implementation in `dev/registry/_semantic_map_loader.py`, public facade in `dev/registry/__init__.py`, and real-filesystem tests in `dev/registry/tests/test_semantic_map_loader.py`. Canonical-home comparison included `_semantic_map.py`, `_semantic_map_validation.py`, `_semantic_map_join.py`, provenance anchor ordering, and the core TOML boundary.

The final implementation reuses public `cadrumo.core.read_toml` and `freeze_toml`, hydrates the existing strict frozen semantic-map schema, refuses non-directories, linked directories and members, non-TOML siblings, malformed TOML, empty fragments and aggregates, filename-to-fragment-id drift, duplicate fragment identifiers, modelo/design conflicts, and every record-anchor, record-id, field-anchor, and field-id collision. Compilation inspects fragments in lexical filename order and canonicalizes compiled records and entries by the established semantic keys. The facade exposes one loader without a compatibility alias. No legacy, generated export, parser intermediate, render profile, neighbouring map, or production registry loader is consulted.

Independent final evidence passed all 20 loader tests and 58 selected loader, semantic-schema, and development-path-isolation tests. Focused Ruff passed, and strict scoped BasedPyright reported zero errors, warnings, or notes. The broader semantic validation/join lane produced 31 passes and 19 setup errors, all before S42 behavior because concurrent source `eu-your-europe-vat-rates-2026-07-13` has a byte-count mismatch. That peer registry-data drift is not an S42 failure.

## Findings

### exact-anchor-order-drift | medium | Entry canonicalization swapped source cell and ordinal precedence

The initial review found `_entry_key` ordering `(sheet, source_row, ordinal, source_cell, record_identity, export_field_id)`, while validation, join, and provenance consistently define the exact field-anchor order as `(sheet, source_row, source_cell, ordinal, record_identity)`, with export field id appended where needed.

Resolution: **RESOLVED.** The loader now uses the established cell-before-ordinal key. A real persisted case places two entries on the same sheet and row with intentionally opposed cell and ordinal order and asserts the canonical cell-first result.

### reviewability-gates-do-not-bind | medium | Required ordering, strict-hydration, and no-fallback proofs were incomplete

The initial creation-order test could not observe filename traversal order because records and entries were independently canonicalized. Persisted strict hydration lacked unsupported schema-version, scalar non-coercion, and nested-extra mutations. The original AST check examined a small exact import set and bare-name calls only, leaving aliased, attribute-call, private-import, and facade-alias regressions insufficiently guarded.

Resolution: **RESOLVED.** Lexical filename order is now observable through two invalid fragments created in reverse order, with the first lexical filename required in the refusal. Persisted tests refuse schema version 2, string-to-integer coercion, and an unknown nested anchor fact. The structural proof now asserts exact direct imports, exact imported symbols by module, resolves name and attribute call targets through aliases before checking forbidden loaders, and asserts the exact facade export list plus object identity of the sole public `load_semantic_map`. Real single-file, linked-directory, and linked-fragment fallback surfaces also refuse.

## Recommendations

Accept `W04.P07.S42` as passing formal review. Preserve the single public loader and facade entry, canonical core TOML owner, existing semantic schema homes, canonical exact-anchor ordering, global collision refusal, strict persisted hydration, linked-path refusal, and normalized structural no-oracle guard as the regression boundary for later authored semantic maps.
