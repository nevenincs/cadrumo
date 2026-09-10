---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b2595338e4dc675171cb983e1778f0b8e566580df3f521045a2303215444062c'
step_id: 'S37'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Position the materialiser inside typed construction immediately after the raw editions resolve and BEFORE per-edition localization enrolment, AND make the label catalogue inherit alongside the declarations in the same change. Locale keys are edition-scoped, so an inherited row enrolled before localization takes the successor's key — the right shape — but has no successor-keyed catalogue entry, and the lookup raises rather than falling back. Rows inheriting while labels do not is not a complete edition. Reuse the shipped locale cascade, which already resolves base, override and exact on this same lineage field. Proof: a migrated edition's locale keys match its pre-migration keys AND every casilla still yields a non-empty label under the historical-epoch sweep that already asserts exactly that.

## Scope

- `src/cadrumo/domain/calculations/registry/_loader_internals.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_label_inheritance.py`
- `verify:` `uv run --no-sync pytest test_casilla_label_spanish_source_coverage.py test_localization_continuity_tier_is_reached.py test_revision_edition_materialisation.py test_revision_predecessor_declaration.py test_revision_predecessor_forest.py test_revision_label_inheritance.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on both files -> `pass`

## Notes

- An inherited casilla carrying aliases is refused at load, because an alias label resolves through one key with no fallback chain. No corpus casilla declares aliases today.
- Inherited rows gain one key in `localization_keys`, the stated edition's occurrence key, between the row's own occurrence key and its continuity key. A typed-equality round-trip gate over a migrated edition sees that extra key, because the field is excluded from dumps but pydantic equality still compares it.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The reviewer persona could not be launched; the orchestrating session reviewed the loader diff against the ADR. Each inherited row's label origin is carried beside the closed raw shape, and it is the edition that last stated the row, not the adjacent one. The shipped cascade resolves the fallback, which still raises when no key resolves. Re-run: the materialisation, label-inheritance, forest, date-agreement and cache tests (39 passed); the historical-epoch label sweep `test_casilla_label_spanish_source_coverage.py` (2 passed); `registry verify` exit 0; ruff and ty clean.
