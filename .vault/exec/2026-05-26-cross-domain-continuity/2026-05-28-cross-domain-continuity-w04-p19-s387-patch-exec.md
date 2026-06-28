---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-28
modified: '2026-05-28'
step_id: S387
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-m210-irnr-full-engine-adr]]"
---

# `cross-domain-continuity` `W04.P19.S387.patch` (M210 registry-load fixes)

Companion to the S387 initial commit (602b0cdfb). Three registry-load failures surfaced after the initial M210 skeleton landed; this patch addresses each.

Commit: `7a270e4ed`

- Modified: `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas/0001-casillas.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/workbook_parity_refs/0001-workbook_parity_refs.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/application_links/0001-application_links.toml`

## Description

The S387 initial commit declared six casillas with `input_kind = "manual"` against the registry's strict revision schema, but the loader contract required either (a) a matching formula entry for each manual casilla, or (b) a manual-input fallback wired through. The Phase 1 ADR D5 hygiene-deferral note explicitly carved out the manual-input fallback as the Phase 1 posture (formulas land at S388), so the loader-side wiring needed to be made explicit.

Three fixes landed in this patch:

1. **Manual-input fallback on the casillas TOML.** The casillas declarations were updated to be compatible with the loader's manual-input fallback path, so the registry validates cleanly even though no formula entries are authored. The header comment was extended to document the manual-input posture and reference the S388 future commit that flips the casillas back to `input_kind = "computed"`.

2. **workbook_parity_refs fragment.** The registry's revision schema requires every revision to declare its workbook parity references (the AEAT-published worksheets the engine will be compared against during the testimonial replay phase). The Phase 1 fragment declares the parity ref for the M210 general / ue_residente computation chain.

3. **application_links fragment.** The registry schema requires every revision to declare its application-link surface (the wiring between casillas and the calculate / verify / file CLI verbs). The Phase 1 fragment wires the six skeleton casillas through the manual-input application path so the M210 work-create surface can route through the existing Path-B refusal stub until S388 lands.

## Why these were not in the initial S387 commit

The initial commit author was working from the m210-irnr-full-engine ADR D2 casilla chain spec but did not exercise the registry loader against the new TOMLs before commit. The loader's three-way contract (formula present, OR manual-fallback wired through casillas TOML, AND workbook_parity_refs + application_links declared) was not visible until the load actually ran. The patch addresses the entire contract.

## Connection to the S398 DAG-correctness lesson

The S398 rollback record at `2026-05-28-cross-domain-continuity-W04-P19-S398.md` captures the parallel lesson on the calculation side: registry authoring must ground against the actual loader / formula DAG contract before committing, not against the regulatory text alone. The S387 patch is the registry-load-contract analogue of that lesson. Authoring discipline: run the registry validator against the new TOMLs before commit so the loader contract is exercised.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: registry loader is the strict pydantic boundary; the patch makes the M210 TOMLs satisfy the contract cleanly.
- G3 user messages via tr(): N/A; registry data.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: workbook_parity_refs and application_links are schema-required fragments, not compatibility scaffolding.
- G6 no tautological tests: registry-load contract is exercised by the existing registry validation suite; no new tests needed at this leaf.

## References

- Parent: S387 initial commit at 602b0cdfb.
- ADR: m210-irnr-full-engine (D2 casilla chain, D5 manual-input + Path-B refusal posture).
- Lesson cross-reference: S398 record (registry authoring must ground against loader contract before commit).
- Surface: `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/`.
