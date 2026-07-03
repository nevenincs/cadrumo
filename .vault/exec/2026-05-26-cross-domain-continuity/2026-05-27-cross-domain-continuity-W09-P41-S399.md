---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-06-29'
step_id: S399
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W09.P41.S399`

Author the TRLIRNR legal catalogue supporting M210 Phase 1 (post-Path-B stub) and stage the consolidated-text HTML corpus for the citation surface.

Commit: `8dce6db35` (architect-2)

> 2026-06-29 currentization: this exec record describes the original
> S399 commit. The current registry has since expanded the IRNR catalogue
> to include art. 13.1.h and art. 25.1.b, populated non-empty
> `required_text`, and corrected art. 25.1.f to the unconditional
> dividend/interest/capital-gain income-class rate. Do not interpret
> art. 25.1.f as a third-country or UE/EEE residency split.

- Modified: `src/aeat/_data/registry/aeat/legal/irnr.toml`
- Modified: `src/aeat/_data/corpus/normatives/html/trlirnr-rdleg-5-2004.html`

## Description

Authored five `[legal."trlirnr-rdleg-5-2004:art-N"]` catalogue entries grounded in BOE-A-2004-4527 (RDLeg 5/2004), the consolidated TRLIRNR text:

- `art-2` — ámbito de aplicación territorial; foral and Canarias/Ceuta/Melilla carve-outs; foundation for IRNR territorial attribution.
- `art-10` — representante fiscal mandate for non-resident filers.
- `art-24` — base imponible.
- `art-25.1.a` — UE/EEE rate split numerator.
- `art-25.1.f` — unconditional dividend/interest/capital-gain
  income-class rate.

Each entry carried `evidence_tier=legal_authority`, `authority=boe`, `kind=real_decreto`, `corpus_ref` pointing at the consolidated-text HTML anchor, `document_id`, `article`, `permalink`, `published_at`, `effective_from`, and `reviewed_at=2026-05-27`. At the time of this commit, `required_text` was intentionally empty for Phase 1 per the m210-irnr-full-engine ADR D5 hygiene-deferral note. Current registry state supersedes that hygiene deferral: the live IRNR legal rows carry corpus-checked `required_text` for the implemented branches.

A header comment on `irnr.toml` carries two correctness anchors:

- Art. 25.1.b (pensiones special tarifa) was RESERVED for task #229 follow-on authoring in this commit; it is authored in the current registry.
- An earlier draft of the M210 ADR mis-cited "TRLIRNR Art 47" for the representante mandate; the correct citation is Art. 10. Art. 47 (sucesión en deuda tributaria) is out of M210 Phase 1 scope. The parallel LGT representante authority is `ley-58-2003:art-47` if a future cross-LGT surface needs it.

## Verification

- Catalogue loads cleanly under the registry validation pipeline.
- Cross-references from the M210 stub refusal text and the future per-row source-jurisdiction gating (S385b, deferred) will resolve against these article IDs.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: catalogue authoring is data; loader enforces schema.
- G3 user messages via tr(): N/A; corpus + catalogue data.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: new catalogue entries follow the existing `[legal."<doc>:<art>"]` shape.
- G6 no tautological tests: catalogue-only commit; no tests added.

## References

- ADR: m210-irnr-full-engine (D5 hygiene-deferral for required_text patterns)
- Catalogue: `src/aeat/_data/registry/aeat/legal/irnr.toml`
- Corpus: `src/aeat/_data/corpus/normatives/html/trlirnr-rdleg-5-2004.html`
- Deferred: Art. 25.1.b for task #229 (Felipe state-pension special tarifa)
