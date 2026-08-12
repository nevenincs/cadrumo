---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:3b6471fe7e62776930cde8222d8b5b4ba87ea939f8d3d6ad3273c17ac814f5f8'
step_id: 'S57'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Integrate the strict core-owned discriminated FilingProjectionRef union atomically through CasillaFieldKind.PROJECTION, projection_ref payload semantics, semantic-map and registry schemas and loaders, provenance, generator, renderer dispatch, and the S47-S50 projectors, deleting description-regex, section, slot, offset, numeric, neighbouring-field, string-key, and legacy inference

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/filing/`
- `dev/registry/`

## Description

- Establish one strict core `FilingProjectionRef` union and exact persisted-wire compiler.
- Route semantic-map and registry TOML loaders through the single compiler and reject scalar coercion.
- Carry `projection_ref`, projection-row repeat mode, and occurrence requiredness through schema, provenance, generation, and rendering.
- Route prorrata, differentiated-deduction, simplified-regime, and exonerado-390 rows through exact typed references.
- Delete description, section, offset, numeric-neighbour, string-key, and compatibility inference.
- Separate explicit non-applicability blanks from applicable missing projector output.

## Outcome

The projection boundary now has one canonical typed owner and one exact persisted compiler. Seven closed union members cover every S47-S50 projection family. Both authored loaders reject string, float, and boolean slot coercion. Applicable missing values remain absent and refuse rendering, while each owning family emits blanks only for an explicit non-applicability decision.

Semantic records now own projection-row repetition and strict occurrence requiredness. Both values participate in semantic-map provenance and generated export records. Required records refuse zero occurrences; optional non-claimed records emit no bytes. Generator and renderer proofs cover both required states.

The expanded focused lane passed 171 tests. Scoped Ruff, Ruff formatting, BasedPyright, diff checks, registry verification, and duplication audit passed. Registry verification covered 73 modelos, 94 revisions, 16,800 casillas, and 1,385 formulas. The duplication audit found no clones across 1,506 files. The Spanish-IVA conformance gate passed five tests.

Formal re-review approved the implementation after all three original HIGH findings were closed. The append-only audit retains the findings and their resolution evidence.

## Notes

The first review correctly found permissive Pydantic coercion, blanket blank pre-seeding, and lost DP30302 occurrence identity. The second review found that repeat mode alone was insufficient because generated records still defaulted to required. Each defect was corrected at its canonical authority rather than patched at a consumer. No compatibility alias, tolerant reader, or parallel projector was retained.

### Reconciliation of the parallel execution

This step was executed twice in parallel on diverged history, and the two executions were reconciled into one canonical result rather than one side being taken wholesale.

Carried over from the second execution, because it is stricter or was genuinely absent here:

- **Identity strings are refused, not normalized.** The second execution remediated a review finding that persisted string identities were being silently normalized; this lane had reached the same surface through a `strip_whitespace` model setting, which coerces instead of refusing. The refusing contract is canonical, per "refuse, do not tolerate", and `projection_kind` is now a required discriminator with no default rather than a defaulted field. Every construction site across the tree was swept to pass it explicitly.
- `filing_projection_ref_casilla_id`, which returns the numbered official endpoint carried by a reference; this lane had no equivalent.
- The slotless operaciones-terceros declarability marker, and the typed dispatch replacing the remaining inference-based Modelo 303 projector identities.
- `application/filing/_projection.py` as the typed filing-projection plan owner. `application/filing/_m303_regimen_simplificado.py` was deleted in the same change, proven subsumed: the surviving module calls `project_m303_regimen_simplificado_rows` directly and re-homes the source-ownership check into `_require_regimen_snapshot_matches_registry`. One canonical home, no bridge.

Deliberately not carried over:

- The second execution deleted the DID-isolated compatibility test. That test is the **only** proof in the tree that a DEVOLUCION draft never leaks the charge IBAN and vice versa, so deleting it would have lost real coverage. It was instead retargeted onto the real bundled 303 snapshot by identity, supplied with the `M303FilingFacts` the renderer now demands, and pointed at `_render_layout` and `_filing_producer_values`. It also still carries the official DP303DID thirteen-row corpus-parity assertion against `aeat-dr-303-2026`'s sha256.

The second execution's note that repository-wide static analysis reported "duplicate imports in untouched registry modules" is now closed: those were merge artifacts of the same class this reconciliation had to sweep, where a clean auto-merge kept both sides' identical additions. A tree-wide `ruff check --select F` sweep reports zero redefinitions and zero duplicate parameters or keywords.
