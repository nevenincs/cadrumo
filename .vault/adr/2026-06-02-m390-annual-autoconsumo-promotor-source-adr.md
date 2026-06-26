---
tags:
  - '#adr'
  - '#m390-annual-autoconsumo-promotor-source'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
  - '[[2026-06-04-m390-annual-autoconsumo-promotor-source-research]]'
---


# `m390-annual-autoconsumo-promotor-source` adr: previous_filing aggregation over four quarterly M303 filings | (**status:** `accepted`)

## Authoring note

Re-author after PM confirmed prior Write did not persist. Authored via Write tool — same bash constraint as the prior ADRs this campaign. Commit-bot validates via `vault check all`.

## Problem statement

`test_binding_prefill::test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations` fails by −21 EUR. Root cause traced by coder1-2:

- M303 quarterly's `iva.cuota-devengada-total` formula now sums `iva.autoconsumo.promotor.cuota` (added per the autoconsumo-promotor work).
- M390's annual mirror `iva.anual.cuota-devengada-total` does NOT sum the parallel autoconsumo total.
- M390's `reconciliacion-303` binding (sourced from M303's `iva.resultado-regimen-general`) carries the autoconsumo cuota (+21); M390's own `regimen-general` lane does not. The Δ = −21 surfaces at the operator-facing reconciliation.

Fix requires a new binding source on M390 that produces the annual autoconsumo-promotor base (so M390's annual cuota mirrors the parallel quarterly sum). The design call is the source shape.

## Decision: Option (b) — previous_filing aggregation over four quarterly M303 filings

`modelo-390-annual-autoconsumo-promotor-base` is a registry binding with `source = "previous_filing"`, selector pulling `iva.autoconsumo.promotor.base` from the four M303 quarterly filings for the same fiscal year, aggregated via `op = "sum"`.

### Why (b)

1. **Semantic correctness.** M390 IS the annual summary of four quarterly M303 filings. Per AEAT M390 instructions (Orden HAC/171/2025 and predecessors), every M390 casilla aggregates over the four trimestres' equivalent M303 casillas. The autoconsumo-promotor base is no exception — it's a quarterly-aggregable concept (Art. 9.1.c LISIVA recognises autoconsumo at the moment of operation per Art. 79.4, which crosses quarters during a single fiscal year). Sourcing from four M303s mirrors the regulatory aggregation directly.

2. **Precedent exists.** M390's existing binding suite at `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/bindings/0001-bindings.toml` ALREADY uses `previous_filing` selectors against quarterly M303 sources. The new binding follows an established pattern, not a novel one.

3. **Operator UX.** Option (a) (profile-sourced manual transcription) would re-introduce the per-filing transcription burden M390 was designed to eliminate. An autonomo with autoconsumo-promotor operations would have to manually copy the annual base from their four quarterly filings into M390. The reconciliation test catching the −21 today would catch operator transcription errors tomorrow — same failure mode, different surface.

### Why not (a)

Profile-sourced manual transcription is simpler to author (one binding entry, no selector) but violates the M390 architectural intent (annual = Σ quarterly). Reject.

## Consequences

- New binding: `modelo-390-annual-autoconsumo-promotor-base` (~10 LOC TOML).
- New formula edge: M390's `iva.anual.cuota-devengada-total` adds the autoconsumo-promotor cuota term derived from the new base × 21% IVA rate (mirrors M303's `modelo-303-autoconsumo-promotor-cuota` formula).
- New casillas if M390 doesn't yet expose semantic-keyed annual autoconsumo concepts (~5-7 registry TOMLs total per coder1-2's diagnosis).
- Test passes: the M390 prefill now mirrors the M303 quarterly sum exactly; Δ = 0.
- Anti-tautology gate: mutate one of the four M303 quarterly `iva.autoconsumo.promotor.base` values, assert M390's annual binding updates correspondingly.

## Dispatch

Hand registry-authoring to coder1-2 (full M303↔M390 context). Single commit, ~5-7 TOML edits + 1 anti-tautology test.

## Status

Accepted and in force. The `previous_filing`-over-quarterly-M303 annual fold-in this
ADR establishes aligns to the canonical carry/fold-in direction in the PHASE ADRs (not
a central apex doc): the future phase-2.3 (fold-in/carry) ADR unifies it with the one
compensación-carry mechanism anchored on the foundational
`live-iva-compensation-wallet-adr`. This ADR's arithmetic stands; phase 2.3 is the
canonical direction.
