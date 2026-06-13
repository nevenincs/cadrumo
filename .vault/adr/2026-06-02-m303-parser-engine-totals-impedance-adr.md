---
tags:
  - '#adr'
  - '#m303-parser-engine-totals-impedance'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-06-02-m390-annual-autoconsumo-promotor-source-adr]]"
  - '[[2026-06-04-m303-parser-engine-totals-impedance-research]]'
---


# `m303-parser-engine-totals-impedance` adr: parser extracts primitives; engine computes totals | (**status:** `accepted`)

## Authoring note

Authored via Write tool — same bash-quoting constraint as the prior five ADRs this campaign. Commit-bot validates via `vault check all`.

## Problem statement

47 M303 verification-chain reds + 3 carry-forward reds cascade from a single architectural mismatch:

- M303 PDF extraction profile populates casillas `27` (Total cuota devengada) and `45` (Total a deducir) at the parser boundary.
- Engine formulas for `iva.cuota-devengada-total` and `iva.cuota-deducible-total` compute the same totals from primitives (`iva.repercutido.*`, `iva.soportado.*`).
- Test fixture's `_COMPUTED_CASILLAS_M303` discards both totals as "computed", so the parser-supplied 27/45 are dropped even when present.
- Net: every M303 verification chain sees `iva.resultado-regimen-general` = 0 − 0 = 0, cascading to boxes 64/66/69/71 = 0; credit-scenario tests fail because `iva.resultado` is 0 instead of negative.

PM attempted Route A (parser-side id rewrite from `27` → `iva.cuota-devengada-total`) and reverted: test still discarded the totals AND the deducible got double-summed where the parser ALSO supplied the totals while the engine computed them separately.

## Forces in tension

- **Dual-keying ADR (`2026-06-01-m303-form-vs-semantic-casilla-dual-keying`)** ratified that `casilla.id` is the canonical engine key. Parser-populated values land in the same `casilla_values` mapping the engine consumes.
- **Engine-vs-parser authority**: when both parser and engine produce a value for the same casilla, the existing infrastructure has no documented arbitration. The current accidental behaviour (parser writes, engine then overwrites OR test discards) is what produces the 50+ reds.
- **PDF extraction fidelity**: AEAT publishes the M303 form with totals printed on the page. Parsing those totals is operator-trustworthy data; the operator filed those exact values. Discarding them in favour of engine-recomputed primitives discards regulatory evidence.
- **Primitive availability**: not all M303 PDFs expose primitives in extractable form. The `iva.repercutido.general / reducido / super-reducido` triple is operator-supplied per AEAT diseño-de-registro, but synthetic-PDF fixtures today don't include them.

## Decision: Route A — parser extracts primitives; engine computes totals

The architectural cleanest answer is the original "parse primitives, compute totals" pattern. Specifically:

1. **Parser extracts primitives only.** Update the M303 extraction profile at `0001-modelo-303-declaracion-pdf.toml` to remove the `27`/`45` total-extraction rules and instead extract primitives by casilla id: `iva.repercutido.general`, `iva.repercutido.reducido`, `iva.repercutido.super-reducido`, `iva.autorepercutido.intracomunitaria`, `iva.autoconsumo.promotor.cuota`, `iva.soportado.interiores`, plus the other deducible primitives.

2. **Engine computes totals from primitives.** `iva.cuota-devengada-total` and `iva.cuota-deducible-total` stay as `input_kind = "computed"` with their existing formulas. The dual-keying ADR's invariant (formulas reference casilla.id only) is preserved.

3. **Form-numbered casillas 27/45 are documentation only.** Per the dual-keying ADR D2-D3: form-numbered references in labels and `export_refs` carry the operator-facing form-page identity, but the engine resolves via semantic id. The parser-side extraction targets the semantic-id primitives directly.

4. **Synthetic-PDF fixture updates** add the primitive form fields. ~5-10 fixture updates across the verification-chain test suite. Existing fixtures that supply only totals get supplemented with primitive breakdown matching the AEAT-published form fields.

5. **`_COMPUTED_CASILLAS_M303` correctly retains** `iva.cuota-devengada-total` and `iva.cuota-deducible-total` as computed because the engine genuinely owns them. No test-fixture change needed at the discard list.

## Why not Route B (parser-supplied overrides)

Route B requires engine support for "input overrides formula" policy. That's a new arbitration surface with project-wide implications. Today's engine treats `input_kind = "computed"` as "engine owns this casilla absolutely"; turning that into a conditional override introduces:

- A new schema field per casilla (`override_allowed: bool`?) — schema extension cost.
- A new arbitration rule at engine evaluation time — what if parser AND engine produce values? Last-write? Parser-wins? Engine-wins? Each policy is an architectural decision that ripples to every modelo.
- Test fixtures must encode the policy choice; the current `_COMPUTED_CASILLAS_M303` becomes load-bearing in a way it isn't today.

Route B is the route to a different architecture, not a fix for the current one. Reject for this Step; reserve as future-hardening direction if M303 turns out to be the first of many parser-fidelity-vs-engine-recompute axes.

## Why not Route C (`.from-pdf` semantic siblings)

Route C introduces parallel casilla ids that shadow the canonical engine ids. Two problems:

- Violates the dual-keying ADR's "one canonical key per concept" invariant. Adding `iva.cuota-devengada-total.from-pdf` alongside `iva.cuota-devengada-total` is exactly the third-keying-axis the dual-keying gate (#134) refuses.
- Doesn't solve the verification-chain test failure — the engine still computes `iva.cuota-devengada-total` from primitives the parser doesn't populate, so the 0-cascade persists.

Reject.

## Consequences

- Extraction profile: ~10 LOC edit removing 27/45 rules + adding ~6 primitive-id extraction rules.
- Synthetic-PDF fixtures: ~5-10 updates adding primitive form-field values matching AEAT-published form layout.
- Test fixture `_COMPUTED_CASILLAS_M303`: NO CHANGE. The discard list correctly retains the computed totals.
- 47 verification-chain tests pass once the primitives flow end-to-end through the engine.
- 3 carry-forward tests pass downstream of the chain.
- Anti-tautology gate: mutate one primitive in a fixture, assert the total updates correspondingly; prove the test consumes the engine computation, not a stale fixture total.

## Migration path

Single atomic commit per the engine-and-fixture co-landing rule (the parser change and the fixture changes must land together; either alone breaks the suite).

Dispatch to coder with full M303 context. Estimated ~80 LOC across the extraction profile + the ~5-10 synthetic-PDF fixture updates + the anti-tautology test addition. ~1-2 commits.

## Out of scope

- The Ley-31/2022 vs LIS-Art.29.1 micro-empresa rate question (separate task; doesn't intersect this parser/engine fix).
- M390 annual autoconsumo binding (separate ADR `2026-06-02-m390-annual-autoconsumo-promotor-source-adr`).
- Engine-side input-overrides-formula policy (Route B future-hardening direction).
