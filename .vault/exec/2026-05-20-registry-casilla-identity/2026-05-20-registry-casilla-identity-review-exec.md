---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` Code Review

Holistic safety, intent, and quality audit of Phase P02 — the validator
and reference-resolution changes. Scope: commits `52e3e2ebc` (S04),
`70c43ff71` (S05), `7a84c7379` (S06), `873c588c0` (S07), covering
`_validate.py`, `_runtime_graph.py`, and `test_referential_integrity.py`.

## Status: PASS

No Critical or High findings. The P02 deliverable implements ADR
decision A2b's identity and reference-resolution mechanics exactly, is
crash-free, and preserves single-segment behaviour byte-identically.

## Safety domain

P02-S04 | LOW | `_emit_casilla_identity_failures` is crash-free.
The helper reads `casilla.segmento` (`str | None`) and `casilla.number`
(`str`, required) — no None-dereference. The sort key `(item[0] or "",
item[1])` normalises a `None` segmento. An empty `revision.casillas`
yields no failures. No resource handles, no concurrency.

P02-S05 | LOW | `_resolvable_casilla_references` is crash-free.
Pure set and dict comprehension over `revision.casillas`; an empty
revision yields an empty frozenset. The function is a pure value
producer with no side effects.

P02-S06 | LOW | `_casilla_reference_resolver` and the rewritten
`formula_evaluation_order` are crash-free. `resolver.get(token, token)`
always returns a string; `setdefault` guards the bare-number entry
against an id of the same spelling so an id always wins. The
`TopologicalSorter` contract is unchanged.

## Intent domain

P02-S04 | PASS | The casilla uniqueness invariant is generalised from
the table-driven per-kind `id` duplicate check to a dedicated
`(segmento, number)` pair check, exactly as ADR decision A2b mandates.
The `id` per-kind check is retained because the ADR keeps `id` as the
stable within-revision handle. Single-segment correctness is exact: with
`segmento` unset the pair degrades to `(None, number)`, and a collision
is reported with the bare-number message `duplicate casilla number
'<n>'`, hard-failing the load precisely as the prior duplicate-id check
did.

P02-S05 | PASS | Reference resolution is segment-aware: a token resolves
against a casilla `id` or against a bare `number` that occurs exactly
once on the revision. An ambiguous cross-segment bare number is excluded
and must be named by the segment-qualified `id`. For single-segment
modelos (`id == number`, every number unique) the resolvable set equals
`set(casilla_by_id)` — identical to the pre-change behaviour. This
matches ADR A2b's reference-resolution rule.

P02-S06 | PASS | The runtime graph dependency walk resolves both the
formula `target` and every expression casilla reference through the
segment-aware resolver before building the DAG. `expression_casilla_refs`
itself is unchanged, preserving the contract its other consumer (the
`_validate.py` formula-DAG validator) relies on.

P02-S07 | PASS | Seven real-behaviour tests exercise the live
`RegistryValidator` with constructed modelo material — no mocks, stubs,
skips, or xfail. Non-tautology was proven empirically: with the S05
resolver reverted, the decisive segment-aware-resolution test fails;
the single-segment collision test fails without the S04 helper because
the colliding casillas carry distinct ids.

No plan drift: every Step edits only its declared target file(s) and
implements only the declared change.

## Quality domain

P02 | MEDIUM | Forward coupling for P04, not a P02 defect.
`_formula_runtime.py` builds its formula lookup keyed on the raw
`formula.target` but indexes it with the resolved id returned by
`formula_evaluation_order`. For single-segment modelos the resolver is
the identity, so the keys agree. For the multi-segment Modelo 200 casillas
P04 will register, the lookup stays consistent only if P04 authors each
`formula.target` as the casilla's canonical (segment-qualified) `id`.
The ADR already mandates `id` as the within-revision handle and requires
formula targets to validate against the casilla set, so P04 authoring
will satisfy this. Recorded so the P04 executor authors composite-id
formula targets deliberately.

P02 | LOW | Helper docstrings are thorough and explain the
single-segment-identity rationale. Naming follows the registry module's
established `_emit_*` / `_resolvable_*` conventions and the Spanish-stem
discipline (`segmento`). Algorithmic cost is linear in casilla count —
no hot-path regression.

## Pre-existing issue (out of P02 scope)

`test_schema_hygiene.py::test_registry_tests_do_not_define_schema_authority_objects`
fails: `test_registry_schema.py` constructs `CasillaDefinition`. This
was introduced by P01.S03 (commit `1706b30a2`), is unrelated to and
untouched by P02, and lies outside the P02 file scope. It belongs to a
P01 review or P05 cleanup. Flagged here as inventory only.

## Verdict

P02 is safe to land. All four Steps implement ADR A2b's identity and
reference-resolution mechanics with exact single-segment preservation;
all 26 modelos load valid; the validator, runtime-graph, and
referential-integrity suites pass.
