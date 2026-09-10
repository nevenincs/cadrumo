---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:312da3f51a97c751ac31d24b85c023aa63042a0d9513c2fc6c81c81d1645bd0b'
step_id: 'S16'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Resolve inherited formula and binding references through lineage against the successor edition's own declaration; an unresolvable reference is a validation failure, never an inherited pointer. Proof: a planted dangling reference is refused.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/identifier_lineage.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_inherited_reference_resolution.py`
- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `M` `dev/registry/analysis/delta_minimality.py`
- `verify:` dump of all 128 compiled revisions on one frozen snapshot, resolver disabled vs enabled -> `pass` (byte-identical)
- `verify:` `uv run --no-sync pytest test_revision_inherited_reference_resolution.py` -> `pass` (12); removing the refusal fails 2, removing the resolution fails 5
- `verify:` `uv run --no-sync pytest test_revision_edition_round_trip.py` -> `pass` (66)
- `verify:` `uv run --no-sync pytest` materialisation, reference-defaults, label-inheritance, export-refs derivation, grade-refusal, non-casilla-exclusion, entry-point, cache-fingerprint and delta-minimality suites -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the changed Python files -> `pass`

## Notes

- `test_no_registry_module_exports_a_symbol_it_does_not_define` fails on `_REVISION_SECTION_FIELDS` in `_loader_internals.py`. The alias is already at HEAD; this Step does not touch it.
- `test_no_revision_spans_a_design_relayout` fails with `registry directory changed during cache fingerprinting` while the export lane republishes the live tree.
- The code review is outstanding: the reviewer persona could not be launched from this session.

- The reviewer persona could not be launched; the orchestrating session reviewed the resolver against the ADR. There is one canonical lineage function; the delta-minimality screen's private copy was deleted in favour of it. The lineage is taken against the edition that stated the row, an unresolved inherited reference is refused, and S15 turns the function into the identity. The boundary was widened from hyphen to all four identifier separators; that changes nothing in the corpus. Re-run: 45 fixture tests passed; `registry verify` exit 0; ruff and ty clean. Nine live-corpus tests errored with 'registry directory changed during cache fingerprinting' while the export lane republished trees; they are not attributable to this Step.
