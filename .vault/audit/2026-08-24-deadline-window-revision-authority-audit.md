---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b90286b58fabb01fda478b54fda6537f4f971e8ae071a5b2dd12a35fa32d7315'
related: []
---

# `deadline-window-revision-authority` audit: `W01 P01 implementation review`

## Scope

Reviewed completed steps `W01.P01.S01` through `W01.P01.S04` against the accepted
deadline-window authority ADRs, plan, research, repository boundary rules, and the
commits attributed to the phase. Unrelated changes captured concurrently in those
commits were excluded. The review covered typed qualifier reuse, strict hydration,
semantic identity, public facade exposure, fragmented authoring parity, and focused
tests. The three focused deadline-window test modules pass (12 tests).

## Findings

### overlapping-tipo-scopes | high | Semantic coordinates do not represent the atomic official-code identity used by matching

`DeadlineSemanticCoordinate.tipo_renta_scope` stores the sorted authored tuple as one
set-shaped coordinate. Consequently a window scoped to `("01", "35")` and another
window scoped to `("01",)` have different semantic coordinates even though both match
official code `01`. The planned global coordinate-uniqueness gate therefore cannot make
qualified resolution exact-one; it admits registry state that the later resolver can
only reject as ambiguous at runtime. This contradicts the accepted requirement that
invalid deadline authority be rejected during registry construction. The coordinate or
its validation consumer must express/check atomic official-code overlap, with bite tests
covering bundled-versus-subset and unqualified-versus-qualified overlap semantics.

### duplicate-resultado-hydration | high | Loader and schema independently parse the same canonical enum token

`_compile_deadline_window_qualifiers` converts `resultado_scope` strings to
`ResultDisposition`, while `DeadlineWindowDefinition.resultado_scope` independently
does the same through a `BeforeValidator`. This creates two accepted-token parsers and
two failure envelopes for one registry field, despite the plan's explicit prohibition
on a parallel parser and the schema already being the strict canonical hydration
boundary. The loader-level misplaced-field check also duplicates the strict revision
schema's extra-field refusal. Keep one conversion/validation authority and make the
loader transport the row to it; tests should prove the public load paths receive the
same strict schema verdict rather than pinning a private second compiler.

## Recommendations

- Before implementing global uniqueness, revise deadline identity validation so any
  two windows capable of matching the same fully qualified request are rejected during
  registry construction. Reuse the existing official-code vocabulary; add no code map.
- Remove the loader-owned resultado parser and rely on the strict
  `DeadlineWindowDefinition` hydration boundary, retaining only structural fragment
  assembly in the loader. Exercise single-file and fragmented paths through public load
  functions.

## Resolution

### overlapping-tipo-scopes | resolved

`DeadlineSemanticCoordinate` now represents one atomic request identity: its
tipo-renta axis is one canonical official code (or the unqualified request), never an
authored set. `deadline_window_semantic_coordinates` expands each validated window
through the existing `ResultDisposition` enum and
`M210_TIPO_RENTA_CODE_PROJECTION`. An unqualified axis expands to every request value
it can match, so bundled-versus-subset and unqualified-versus-qualified windows share
an atom and cannot evade the planned global uniqueness gate. Focused tests prove both
overlap shapes without introducing another code vocabulary or resolver.

### duplicate-resultado-hydration | resolved

The loader-owned qualifier compiler and its second `ResultDisposition` parser were
removed. Both single-file and fragmented public load paths now transport authored
rows unchanged into `DeadlineWindowDefinition`, the sole hydration and failure
boundary. The loader's custom misplaced-field check was also removed because strict
`ModeloRevision` extra-field refusal already supplies that invariant. Focused tests
prove identical schema verdicts for an invalid resultado token across both public load
paths and retain coverage for strict rejection of misplaced qualifier fields.

Validation: Ruff passed for the five touched registry modules/tests; focused pytest
passed with 14 tests across semantic-coordinate, loader, and qualifier-schema coverage.
No HIGH or CRITICAL findings remain open in this P01 review slice.
