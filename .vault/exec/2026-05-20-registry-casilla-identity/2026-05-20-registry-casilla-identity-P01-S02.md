---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S02'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---



# `registry-casilla-identity` `P01.S02`

Documented the `segmento` field contract on `CasillaDefinition` as a
field description and a class docstring note.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`

## Description

`CasillaDefinition` gained a class docstring stating that a casilla's
identity is the pair `(segmento, number)`: single-segment modelos leave
`segmento` unset and `number` alone is unique within the revision;
multi-segment AEAT modelos (e.g. Modelo 200) reuse the same five-digit
`number` across distinct record segments and carry the AEAT
record-segment code in `segmento` to disambiguate.

The `segmento` field gained a `description` argument restating the same
contract at the field level: it carries the AEAT record-segment code
(e.g. `DP200014`) for multi-segment modelos, is unset for single-segment
modelos, and the casilla identity is the `(segmento, number)` pair.

No plan, phase, wave, or ADR identifiers were embedded in the source.
The documentation uses stable tax-domain vocabulary (casilla, modelo,
record segment) that remains true independent of the current project
plan, per the source-hygiene rule.

## Description (collision)

The shared-worktree collision check (`git diff` against
`_schema.py`) returned clean before the edit; no non-authored
uncommitted WIP was present.

## Tests

`uv run --no-sync ruff check` on `_schema.py` passed. The full registry
schema test module (`test_registry_schema.py`, 66 tests) passed against
the bundled registry corpus, confirming the documentation-only change
disturbs no load or validation path.
