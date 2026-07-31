---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:d661ca683a199fd58cab142fbb74982aa6e4e499ac1448e6ccee23446878c140'
step_id: 'S256'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Build describe, casilla listing, and formulas from shared typed projections while preserving separate casilla-detail and bindings reports unless code-level substitutability is proven

## Scope

- `src/cadrumo/domain/calculations/registry/_queries.py`

## Description

- Adopt the stranded projection refactor found in the working tree alongside the typed context.
- Confirm describe, casilla listing and formulas each build from one shared builder on both routes.
- Test whether the bindings report and the single-casilla detail are substitutable at code level before deciding to merge or keep them.

## Outcome

Implemented, adopted rather than authored, with the substitutability question answered against the code.

Each shared report now has exactly one builder taking the typed context. Describe, the casilla listing, the formula listing and the bindings listing are each assembled in a single function that both the scoped and unscoped query methods call. The bindings case is the clearest gain: the scoped method previously re-derived its own definition and snapshot and constructed the report inline, while the unscoped method constructed a second copy from different inputs, so the two spellings of one report could drift apart without anything detecting it. Both now call one builder. The filter arguments on the casilla listing are still passed through to the shared builder rather than being applied at the call site, so sharing the builder did not quietly drop the filtering behaviour, and there is now a test pinning that.

The step allows merging the bindings report and the casilla-detail report only if substitutability is proved at code level. It is not provable, so they remain separate, and the reason is recorded in a test rather than left as an assumption. Their field sets are not in a subset relation in the direction a merge would need. The bindings report carries a row collection the detail report has no field for, and the detail report carries per-casilla grounding the listing has no field for, including the resolved formula expression, the legal and source references and the localized labels. Neither can be projected from the other without inventing data, so they answer different questions and stay distinct. They do share the scope spine they take from the one context, and that agreement is asserted.

The four builders were verified to produce byte-identical rows from both resolution forms against the real registry before the assertions were written, so the proofs describe observed behaviour rather than intended behaviour.

Committed in `003a2f987d`.

## Notes

Semantic CODE search is degraded and reports itself healthy; the module was read directly.

As with S254, the projection refactor was already present in the working tree as uncommitted stranded work and was adopted rather than re-implemented. The substitutability judgement and its test are the part authored here.

This step has no counterpart in the sibling quality-backlog plan.
