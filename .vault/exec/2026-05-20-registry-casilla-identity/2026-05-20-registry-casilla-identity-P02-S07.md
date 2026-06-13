---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S07'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P02.S07`

Added validator tests covering `(segmento, number)` casilla identity and
segment-aware reference resolution.

- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`

## Description

Seven real-behaviour tests were added, all exercising the live
`RegistryValidator` against constructed `ModeloDefinition` /
`ModeloRevision` material — no mocks, stubs, skips, or xfail markers. A
`_segmented_casilla` helper builds a minimal manual casilla with an
explicit `number` and `segmento`.

Identity-uniqueness coverage:

- `test_same_number_distinct_segmento_casillas_validate` — two casillas
  sharing number `00562` under distinct segmento codes (`DP200014`,
  `DP200032`) both validate; the identity pairs are distinct so the
  multi-segment AEAT shape is declarable.
- `test_single_segment_duplicate_number_collision_fails` — two
  segmento-unset casillas with distinct ids but the same number
  collide on `(None, 00562)` and hard-fail. The distinct ids mean the
  per-kind duplicate-id check does not fire; only the generalised
  `(segmento, number)` invariant catches the collision, with the
  bare-number message preserved exactly.
- `test_same_segmento_duplicate_number_collision_fails` — a number
  declared twice within one segmento hard-fails, reported
  segment-qualified.

Segment-aware reference resolution coverage:

- `test_single_segment_bare_number_reference_resolves` — a formula
  referencing a casilla by bare number resolves single-segment.
- `test_bare_number_reference_resolves_when_id_is_segment_qualified` —
  the decisive case: a casilla whose `id` is segment-qualified but whose
  `number` occurs once is resolvable by its bare number, because the
  number is unambiguous within the revision.
- `test_ambiguous_cross_segment_bare_number_reference_does_not_resolve`
  — a bare-number reference to a number reused across two segments fails
  to resolve, forcing the formula to name the intended occurrence by the
  segment-qualified id.
- `test_segment_qualified_reference_resolves_across_segments` — a
  segment-qualified `id` reference resolves cleanly with the number
  reused across segments.

Non-tautology was proven empirically: with the S05 change
(`casillas = set(_resolvable_casilla_references(revision))`) temporarily
reverted to `set(casilla_by_id)`,
`test_bare_number_reference_resolves_when_id_is_segment_qualified`
fails with an `unknown casilla '00562'` validator failure; the S05
change was then restored. The single-segment collision test likewise
fails without the S04 `_emit_casilla_identity_failures` helper, since
the colliding casillas carry distinct ids.

This Step edits only the test module; `_validate.py` and
`_runtime_graph.py` were committed in S04/S05/S06.

## Tests

`uv run --no-sync pytest`: `test_referential_integrity.py` 35 passed
(28 pre-existing + 7 new), `test_modelo_parity_coverage.py` 1 passed —
all 26 modelos load valid. `ruff check` on
`test_referential_integrity.py` clean.

## Shared-worktree note

A concurrent agent introduced uncommitted "Registry hardening" WIP into
`src/aeat/domain/calculations/registry/_validate.py` (a
`CrossDomainSnapshotCheck` Protocol refactor) after the S05 commit. That
WIP is non-authored and was left untouched: the S07 commit uses an
explicit path and includes only `test_referential_integrity.py`. The
S04/S05 helpers in `_validate.py` remain intact and committed under
`52e3e2ebc` / `70c43ff71`.
