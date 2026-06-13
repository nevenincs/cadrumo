---
tags:
  - '#adr'
  - '#synthetic-fixture-primitive-encoding-discipline'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
  - "[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-06-01-verification-fixture-roles-adr]]"
  - '[[2026-06-04-synthetic-fixture-primitive-encoding-discipline-research]]'
---

# `synthetic-fixture-primitive-encoding-discipline` adr: synthetic PDFs encode primitives, not summed totals | (**status:** `accepted`)

## Authoring note

Authored via Write tool — same bash-quoting constraint as the prior 13 ADRs this
campaign. Commit-bot validates via `vault check all`.

## Problem statement

Synthetic-PDF fixtures across the modelo suite encode **operator-summed totals**
on the form-page surface (e.g. M303 prints "Total cuota devengada 12000,00") but
do not print the **primitives** the engine computes those totals from
(`iva.repercutido.general/reducido/super-reducido`, `iva.soportado.interiores`,
etc.). The M303 parser/engine impedance documented in
`2026-06-02-m303-parser-engine-totals-impedance-adr` is the canonical example:
the engine recomputes the total from primitives the parser never extracted, so
the recomputed total is zero, the chain collapses to zero, and 47 verification-
chain tests + 3 carry-forward tests red.

The 2026-06-02 ADR resolved the M303 instance with Route A (parser extracts
primitives; engine computes totals; form-numbered casillas become
documentation only). What that ADR did not resolve is the **cross-modelo
authoring discipline**: should every synthetic fixture going forward print
primitive line items, or just the printed totals the operator sees on the
form? Today's _generate.py file has 15 M303 corpus fixtures plus M115/M123/
M130/M180/M193/M349/M180/M232/M369/M720/M036/M840/M184/M347 fixtures, each
authored to a different printed-form layout. Without a discipline, the next
modelo's chain failure will follow the same pattern.

## Forces in tension

- **Parser fidelity to AEAT-published form layout.** AEAT publishes the
  *justificante de presentación* with the totals printed on the page. A
  fixture that omits the printed total drifts from the AEAT-published
  artefact and silently weakens the parser's regression coverage.
- **Engine-chain exerciseability.** A fixture that prints *only* the total
  cannot exercise the engine's primitive-summation formulas; the parser
  populates the total directly, the engine has nothing to compute from, and
  the verification-chain tests are blind to formula breakage.
- **Operator-visible reality.** A real-world operator fills in primitives
  (per-rate base/cuota rows) and the PDF generator prints both the
  primitives and the summed totals on the same page. The synthetic fixture
  is faithful to the operator's reality only when both layers are present.
- **Anti-tautology gate.** A fixture that encodes only the total and
  asserts the engine reproduces that total is a textbook tautology — the
  test consumes its own input. A fixture that encodes primitives and
  asserts the engine derives the total from them is the non-tautological
  shape.
- **Authoring cost.** Each modelo's primitive row count varies (M303 has
  ~16 base/cuota primitive pairs across three rate brackets; M130 has
  three primitive line items; M184/M347 multi-row models have N primitive
  rows per declared entity). Encoding all primitives is more authoring
  work per fixture.

## Decision: synthetic fixtures MUST encode primitives; printed totals are an additional layer, not a substitute

Going forward, every synthetic-PDF fixture under
`src/aeat/tests/fixtures/justificantes/<modelo>/` MUST print the primitive
casilla line items that the engine computes its totals from, **in addition to**
any printed totals AEAT shows on the published form. The discipline has four
components:

### 1. Primitive coverage is the authoring contract

The synthetic fixture for modelo M MUST print the casilla line items for
every `input_kind` ∈ {`manual`, `derived_from_ledger`} casilla that an
engine formula references as an argument. The fixture author identifies
these by:

- Reading the revision's `formulas` block for every formula with
  `input_kind = "computed"` on its target.
- Enumerating the `expression.args[].casilla` referenced by those
  formulas.
- Filtering to those whose casilla definition has `input_kind` ∈
  {`manual`, `derived_from_ledger`}.
- Printing each of those as a labelled line item on the fixture, with a
  label that the modelo's `declaracion_pdf` extraction profile can
  resolve via `named_label` against the actual AEAT-published form
  vocabulary.

Computed totals (`input_kind = "computed"`) MAY appear on the fixture as
additional printed lines — they are operator-visible reality on the AEAT
form — but the extraction profile MUST NOT target them; the parser
extracts primitives only, and the engine recomputes the total.

### 2. Computed-total label lines are permitted but never extracted

It is acceptable (and AEAT-accurate) for the synthetic fixture to print
lines like "Total cuota devengada 12000,00" because that's what the
AEAT-published justificante shows. What is forbidden is wiring those
printed totals into the extraction profile's `target_casillas`. The
profile points at primitive ids only. The printed totals exist on the
PDF as faithful reproduction of the AEAT form; they are not the
parser's contract.

This separation is the operational expression of the dual-keying ADR's
D2-D3 ("form-numbered references in labels and `export_refs` carry the
operator-facing form-page identity, but the engine resolves via semantic
id"). The form-page totals are documentary; the semantic primitives are
contractual.

### 3. Per-fixture primitive value distribution

The fixture author chooses a per-modelo distribution that:

- Sums to a fixture-stable total via the engine formulas (so the
  verification-chain tests have a deterministic expected total).
- Is realistic-shaped for the modelo (e.g. M303 single-rate filer puts
  all base in `iva.repercutido.general` @ 21%; mixed-rate filer
  distributes across general/reducido/super-reducido in 60/30/10
  proportions; multi-rate is reserved for fixtures specifically
  exercising rate-distribution behaviour).
- Is grounded in the modelo's BOE-published example where one exists,
  and in a documented synthetic-shape rationale otherwise.

The discipline for choosing the distribution lives in a docstring on the
fixture's dataclass, alongside the existing `Non-tautology proof:`
docstring section that every fixture already carries.

### 4. Anti-tautology gate per modelo

The companion test for each modelo's synthetic-fixture pool MUST include
an anti-tautology assertion: mutate one primitive in the fixture, regenerate,
parse, run the engine, and assert that the recomputed total updates
*correspondingly* (not just "changes" — the new total must equal the
sum of the mutated primitives by the registry formula). If this test
ever passes when the engine is broken, every fixture-engine roundtrip in
the suite is tautological.

This generalises the M303 anti-tautology requirement from
`2026-06-02-m303-parser-engine-totals-impedance-adr` to every modelo.

## Migration scope

This ADR governs forward authoring and remediation of in-scope existing
fixtures whose modelo has a working engine-chain test. Specifically:

- **M303**: remediated under the M303-specific ADR. ~15 fixtures regenerate
  with primitive layout. This ADR generalises the discipline.
- **M130**: 12 quarterly fixtures already encode primitives (cas 01-15
  line items) but should be audited for full coverage against the M130
  formula DAG. Likely 1-2 missing primitive print lines per fixture.
- **M180**, **M193**: resumen-anual fixtures already encode primitives
  (perceptores / base / retenciones). Already compliant; documented for
  the audit baseline.
- **M349**, **M180**, **M115**, **M123**, **M232**, **M369**, **M720**,
  **M036**, **M840**: per-modelo audit pass to confirm primitive
  coverage. Most are simple-form fixtures already compliant; the
  exceptions land as targeted patches per the per-modelo migration.
- **M184**, **M347**, **M232** multi-row: row-aware primitive encoding
  per the multi-row materialisation ADR cluster (task #200, #224). The
  primitive layer here is per-row, not per-modelo.

## Why not the alternative ("printed total only, engine bypassed")

The alternative is to accept the parser-populates-total pattern (Route B
from the M303 ADR) project-wide: every parser extracts whatever AEAT
prints on the form, and the engine's "computed" formulas become a
*verification* layer that asserts the printed total equals the
recomputed total within tolerance.

Reject for three reasons:

1. **Loses the formula-coverage signal.** A fixture that supplies the
   total directly cannot fail when a primitive-summation formula is
   wrong. The engine's formula registry becomes documentation that no
   gate exercises end-to-end.

2. **Requires a new arbitration policy.** The "parser supplies value;
   engine also computes value" arbitration is a project-wide
   architectural choice (the M303 ADR's Route B) that ripples to every
   modelo, every casilla, and every export path. Not deciding it for
   the test fixtures bleeds the indecision into production.

3. **Doesn't fit informativa modelos.** Models like M180/M193/M349/M232
   don't have a "total" the engine recomputes from primitives — they
   are pure informativa structures where every printed value IS the
   primitive. The "parser extracts total" rule has no meaning for
   them; the "parser extracts primitives" rule applies uniformly.

## Consequences

- Every new synthetic fixture lands with primitive coverage from day one.
- Every existing fixture audited and brought into compliance on the
  same cadence as the modelo's verification-chain hardening.
- Cross-modelo authoring discipline written into the corpus generator
  module docstring at the top of `_generate.py` referencing this ADR.
- The audit-swarm "calculation-engine grounding" axis (axis 1 from
  `aeat-swarm-audit-cadence`) gains a structured finding shape: "modelo M
  has formulas referencing primitive casilla P; fixture pool for M does
  not print P" — actionable by primitive count.
- The `fixture-provenance-declared-in-sidecar` rule's `provenance =
  synthetic_generated` declaration implies primitive-encoding compliance
  on documents authored after this ADR's accept date (2026-06-03).
  Pre-dating fixtures carry a one-time grandfather grace period until
  their modelo's verification chain is exercised end-to-end.

## Out of scope

- The Route-B input-overrides-formula architecture (rejected by the M303
  ADR and rejected again here for cross-modelo authoring).
- Real-corpus fixtures (`provenance = real_corpus`) carry primitive
  coverage from the AEAT operator's filing, not from the synthetic
  generator. The discipline here is for `provenance =
  synthetic_generated` fixtures only.
- The golden-SHA byte-identity contract for the BOE-fichero export
  surface (separate ADR
  `2026-06-03-fichero-boe-golden-sha-contract-shape-adr`).

## Status

Accepted. The discipline binds every new synthetic fixture and every
remediated pre-existing one. The M303-specific synthetic generator spec
(`2026-06-03-m303-synthetic-generator-primitive-spec-adr`) is the first
concrete application.
