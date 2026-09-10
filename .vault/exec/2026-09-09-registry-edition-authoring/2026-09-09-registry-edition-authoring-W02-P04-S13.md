---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:d9affd5eba332035ba70e0efe2d69d820d7b0f17385375da261cf5ce9ab8aeb4'
step_id: 'S13'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Declare source references and orden references once on the edition, inherited by rows that state none. Proof: a row stating its own overrides; a row stating none inherits; the materialised row is unchanged from today.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_revision_sections.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_manifest_only_placement.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_reference_defaults.py`
- `verify:` `uv run --no-sync pytest` materialisation, label-inheritance, forest, declaration, date-agreement, grade-refusal, authority-grade, review-scope, edition round-trip, corpus round-trip gate, manifest-only placement, schema-family, materialisation entry-point and exclusion, reference-defaults, `dev/registry/tests/test_delta_minimality.py` -> `pass`
- `verify:` 128-revision dump of one frozen registry copy, before and after -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the changed files -> `pass`

## Notes

- A migrated edition that declares `casilla_source_refs` dumps the field, so the edition round-trip gate will report it as a changed edition field until the gate's equality exclusions admit it beside `predecessor`. No edition declares it yet.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The reviewer persona could not be launched; the orchestrating session reviewed the contract against the ADR. `casilla_source_refs` is one manifest-only field, orden references reuse `orden_aplicabilidad`, a stated value replaces the default, and defaults apply after inheritance so an inherited row takes the successor's. The orchestrating session added `casilla_source_refs` to the round-trip gate's equality exclusions (every filled row is still compared). Re-run: 124 passed including the round-trip gate, `registry verify` exit 0, ruff and ty clean.
