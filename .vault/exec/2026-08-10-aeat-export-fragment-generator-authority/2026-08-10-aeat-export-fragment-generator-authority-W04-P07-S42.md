---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:eaa688ebf1286548c4ed9851c586e2851a0422f8f0a321996134526fe0247a7e'
step_id: 'S42'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Define one strict canonical persisted semantic-map fragment format and public loader/facade with deterministic filename-ordered compilation, exact schema validation, duplicate and collision refusal, and real reviewability tests, without consulting legacy export trees or adding aliases

## Scope

- `dev/registry/`
- `dev/registry/tests/`

## Description

- Ground the storage contract in the accepted generator-authority decision, the existing semantic-map schema/join/validation owners, the canonical TOML helpers, and the strict render-profile fragment analogue.
- Define one schema-versioned strict fragment model and compile regular TOML children from a real directory into the existing `SemanticMap` without redeclaring anchors, entries, records, kinds, or identifiers.
- Require `NNNN-<fragment_id>.toml`, identical modelo/design identity, canonical semantic-key ordering, and refusal of empty aggregates, malformed or unknown fields, noncanonical members, links, single-file fallbacks, and every fragment/record/field identity collision.
- Export the semantic-map schema and sole persisted loader from the development facade, with structural guards against parser, render-profile, generated-tree, registry-loader, and alias/fallback dependencies.
- Add real-filesystem tests for deterministic order, strict scalar and nested hydration, exact collision classes, filename identity, schema cutover, link refusal, and the exact public facade.

## Outcome

S42 establishes one persisted meaning-only semantic-map boundary ready for the reviewed Modelo 303 maps. The loader reuses `cadrumo.core.read_toml` and `freeze_toml`, compiles into the pre-existing `SemanticMap`, and never observes parser intermediates, registry snapshots, render profiles, generated layouts, neighbouring maps, or legacy export trees.

The independent formal review initially found two medium issues: the field sort key placed ordinal before cell, and several order/strictness/fallback tests were non-biting. The final implementation aligns with the canonical `(sheet, row, cell, ordinal, record identity, export id)` order and adds adversarial lexical-first-failure, cell-versus-ordinal, unsupported-version, strict noncoercion, nested-extra, resolved-call-target, and exact-facade proofs. The final audit verdict is PASS with no open high, medium, or low findings.

Verification on the final snapshot:

- persisted loader tests: 20 passed;
- selected loader, semantic-schema, and development-path-isolation tests: 58 passed;
- scoped Ruff: clean;
- strict scoped BasedPyright: 0 diagnostics;
- frontmatter: clean.

## Notes

The broader semantic validation/join lane reached 31 passes before 19 setup errors caused by concurrent unrelated byte-count drift for `eu-your-europe-vat-rates-2026-07-13`. No S42 assertion failed, and the peer-owned source was not modified.

Fresh official-binary census for the subsequent Modelo 303 map work found six fixed records per epoch plus the source-declared variable `DP30300` envelope. That exposed the separate S43 parser prerequisite; S42 does not broaden into variable-envelope parsing or author any S19 semantic facts.
