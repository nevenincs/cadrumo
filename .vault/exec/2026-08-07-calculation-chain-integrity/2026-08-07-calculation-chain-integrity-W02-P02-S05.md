---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a2467a39f4c16045713f30f4a178dd63e7355921d6f60b2a49c32236d55ac144'
step_id: 'S05'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---

# Read the modelo-130-relation-regression ADR ruling on bound-casilla zero defaults as direct prior art, nothing in the research cites it

## Scope

- `.vault/adr/2026-05-26-modelo-130-relation-regression-adr.md`

## Description

- Read `2026-05-26-modelo-130-relation-regression-adr` (accepted) in full, including both amendments.
- Extracted the shipped three-state contract (resolved / absent-by-design / missing-error) for observation-backed binding sources (`previous_filing`, `relation_prefill`), enforced by the named `_OBSERVATION_BACKED_SLOT_SOURCES` constant.
- Confirmed the ADR's own final amendment states the scope explicitly: non-observation-backed sources (`profile`, `ledger_*`, invoice, withholding) keep the plain `inputs` fallback unchanged -- the M130 retenciones binding this plan's research measured is exactly that excluded class.
- Read `src/cadrumo/application/calculations/_relation_prefill.py` (`W02.P02.S18`'s target) as the companion authority: a relation with no prior filing legitimately returns `value=None`/`provenance="operator_manual"`, never a zero -- the false-positive floor any new detection mechanism must respect.

## Outcome

The modelo-130-relation-regression ADR is direct prior art, not merely adjacent context: it already solved the identical silent-zero failure class for two binding source kinds and explicitly scoped ledger-backed sources OUT of that fix. This plan's `W02.P02.S06` decision record is therefore framed as extending an already-accepted, already-shipped three-state contract to the sources its own amendment left open, rather than inventing an unrelated mechanism. Findings folded directly into `2026-08-07-silent-zero-regression-screen-adr` (authored under that feature tag, alongside the grounding research, per plan-owner direction).

## Verification

## Notes

Read-only step; no code or test changes. `2026-06-19-silent-zero-base-aggregation-adr` and `2026-08-06-llm-invoice-read-reconciliation-adr` remain the governing records for Waves W03/W04 and are unaffected by this reading.
