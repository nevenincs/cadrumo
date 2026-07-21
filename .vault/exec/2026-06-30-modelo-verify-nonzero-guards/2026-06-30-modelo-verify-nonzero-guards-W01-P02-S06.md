---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Author the modelo-123-2024-base-total-implica-retenciones-total ADVISORY predicate implies_nonzero(["06", "09"]) with legal_refs rd-439-2007:art-90 and ley-35-2006:art-101 on the 2024-y-siguientes revision, recording the aggregate-versus-per-category design decision in the exec record

## Scope

- `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/verification_expectations/0002-verification_predicates.toml`

## Description

- Read the predicate schema (`KNOWN_VERIFICATION_PREDICATE_OPERATORS`, `VerificationPredicateDefinition`) and the M200/M131 reference fragments to confirm the `implies_nonzero` shape, the file-numbering convention (`0001-verification-expectations.toml` already owns the completeness-manifest gate, the new advisory predicate lands in a sibling `0002-verification_predicates.toml`, following the M131 precedent of incrementing past the existing `0001` file rather than colliding with it).
- Read the M123 2024-y-siguientes casillas and formulas: casilla `06` (base total) is computed `04 + 05`; casilla `09` (retenciones total) is computed `07 + 08`. Both totals are independently formula-derived from disjoint manual leaf casillas.
- Resolved the aggregate-vs-per-category design decision (see below) in favour of the aggregate `implies_nonzero(["06", "09"])`, matching the ADR default.
- Confirmed both legal_refs (`rd-439-2007:art-90`, `ley-35-2006:art-101`) already exist in `src/aeat/_data/registry/aeat/legal/irpf.toml` with `review_status = "reviewed"` and a `corpus_ref` resolving to bundled BOE text, per `legal-grounding-verifies-bundled-authoritative-corpus`.
- Authored `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/verification_expectations/0002-verification_predicates.toml` carrying one ADVISORY predicate `modelo-123-2024-base-total-implica-retenciones-total`.

### Design decision: aggregate `06->09`, not per-category `04->07` / `05->08`

Considered both shapes. The per-category guard (`04->07` for dividendos/participaciones, `05->08` for resto de rentas) was rejected because it independently demands a nonzero retencion leaf for EACH base leaf the operator populates, which would false-positive on a filer whose activity concentrates in one category while the registry cannot express category-specific withholding exemptions or rate variations (e.g. the RD 439/2007 art. 90 60% reduction for sociedades de capital semilla applies per-renta, not uniformly). The aggregate `06->09` guard only fires when the WHOLE base total is positive yet the WHOLE retenciones total is zero — the case with no legitimate cause under art. 90's general 19% withholding obligation — while tolerating any legitimate per-category asymmetry the per-category shape would have falsely flagged. This mirrors the ADR's stated default and the M200/M131 precedent of choosing the false-positive-free formulation over the most granular one.

## Outcome

Registry fragment landed and validated: the predicate loads cleanly off the M123 2024-y-siguientes revision snapshot (confirmed via the registry-shape test in S07) with no registry-build validation errors (legal_refs resolve, casilla ids `06`/`09` exist, operator name is a known DSL operator).

## Notes

No incidents. No peer WIP detected on the touched directory prior to authoring (`git status --short` was clean for the M123 registry path before this edit).
