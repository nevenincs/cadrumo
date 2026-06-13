---
tags:
  - '#adr'
  - '#modelo-export-evidence-parity'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-modelo-export-evidence-parity-research]]"
  - "[[2026-06-02-modelo-filing-ledger-snapshot-adr]]"
---



# `modelo-export-evidence-parity` adr: `ledger-evidence-bundled modelo revisions and exports` | (**status:** `accepted`)

## Problem Statement

A modelo calculation revision that derives its casilla values from the ledger
records only a content **fingerprint** of the ledger state it was computed from
(`LedgerFilingSnapshot`: per-transaction SHA-256 plus an aggregate hash). The
fingerprint is sufficient to detect drift, but it is **not evidence**: the actual
contributing transaction data, the operator's manual casilla inputs, and the
FX/derivation fact basis cannot be reconstituted from the revision, and no modelo
export carries them. A human files the modelo outside the application; a
legally-sound filing artefact must therefore answer, from itself, "exactly which
ledger rows and manual entries produced casilla X = N, and on what basis". Today
it cannot. This is a foundational calculation-grounding gap: the fact basis is
absent from the revision's internal state, from the offline export, and from the
online export. This ADR makes the fact basis a first-class, pegged, exportable
part of every ledger-derived modelo revision.

## Considerations

- **Provenance discipline.** The project already mandates that every casilla
  observation carry `legal_refs` / `source_refs` / `formula_id` from registry to
  operator surface, and persists typed envelopes (`CasillaObservation`,
  `CalculationRevision.observations`) rather than flat scalars. Evidence bundling
  is the ledger-side completion of that discipline: the *inputs* must be as
  traceable as the *outputs*.
- **Reuse, do not reinvent.** The contributing-row identity, the snapshot timing,
  and the staleness machinery already exist (`LedgerFilingSnapshot`,
  `compute_ledger_filing_snapshot`, `CalculationRevision.source_transaction_ids`
  + `.ledger_filing_snapshot`). The decision extends these with *data*, it does
  not replace them.
- **Two evidence carriers.** (1) The ledger contributors — typed
  `Transaction`-derived rows that fed the bindings, plus their attachment /
  document-link references. (2) The manual fact basis — operator-entered casilla
  inputs and binding overrides that are not ledger-derived. Both must be
  captured; a casilla is otherwise unexplained.
- **Sensitivity.** Ledger rows are FINANCIAL-sensitivity data. The bundled
  evidence inherits that classification; a redaction projection governs what
  leaves the secure boundary in an operator-shareable export (counterparty,
  amount, tax facts — yes; raw private narrative — redactable per the existing
  output-redaction discipline).
- **Reference vs. bundle.** A legally-sound artefact bundles the evidence; a
  lighter operator export may instead carry a resolvable in-system reference
  (revision id + snapshot fingerprint) that the application can re-expand. Both
  are permitted; the bundled form is the default for filing artefacts.

## Constraints

- **Strict-frozen pydantic, core types.** New records are `STRICT_FROZEN_CONFIG`,
  reuse `core` enums / errors / exceptions, and follow the relative-import +
  hexagonal-layering conventions (pure records in `domain/modelos/`, capture in
  `application/aggregation/`, export materialisation in `application/storage` +
  `adapters/outbound/`). No `dict[str, Any]` at the boundary.
- **Persistence boundary.** The evidence rides inside the encrypted
  `CalculationRevision` envelope through `SecureObjectRepository`; it must carry
  its own strict roundtrip test (save → load → strict equality) with every
  defaultable field populated to a non-default value, per the roundtrip
  discipline. A larger envelope must stay within repository payload limits — the
  evidence projection is bounded (tax-relevant fields only), not the full raw
  record.
- **Parent-feature stability.** Depends on the accepted
  `modelo-filing-ledger-snapshot` ADR (stable, shipped) and the registry
  authority flow (stable). It does not depend on the live-Google workstream;
  offline bundling lands first and is the foundation the online export consumes.
- **No tautology.** Evidence-roundtrip and casilla-attribution tests assert real
  reconstitution (the bundled rows re-derive the casilla), never numbers
  hand-computed from the same formula.

## Implementation

A new pure domain record — provisionally `LedgerFilingEvidence` — extends the
snapshot layer in `domain/modelos/_ledger_filing_snapshot.py` (or a sibling
module) and is referenced from `CalculationRevision` alongside the existing
`ledger_filing_snapshot`. It carries, per contributing transaction, a typed
**evidence projection** (the tax-relevant `Transaction` fields that moved a
casilla — signed amount, currency, direction, base/IVA/rate/category, irpf
category, EU member state, FX conversion, lifecycle, business proportion — plus
`legal_refs`/`source_refs` already on the observation and the attachment /
document-link ids), and a parallel set of **manual fact-basis** entries (operator
casilla inputs and binding overrides not sourced from the ledger). The aggregate
`snapshot_fingerprint` already present remains the content address binding the
evidence to the fingerprint snapshot, so a mismatch is detectable.

Capture happens in the application aggregation layer at the same verify-time
point that `compute_ledger_filing_snapshot` runs, reading the live catalogue once
and projecting the resolved `source_transaction_ids` into the typed evidence rows
plus the operator inputs threaded through the calculation. The revision persists
the evidence inside its encrypted envelope.

Exports consume the bundled evidence uniformly. The calc-sheets plan gains an
**Evidencia** surface (a dedicated, protected tab in the workbook) that lists,
per casilla, the contributing rows and manual entries with their amounts and
legal grounding — and a machine-readable evidence sidecar accompanies the
artefact. The flat / offline xls export and the online Sheets export both read
the same bundled evidence so offline and online artefacts are evidence-identical.
An export of a ledger-derived revision that lacks bundled evidence (or a
resolvable reference) is refused.

## Rationale

The research established (finding B) that the fact basis is genuinely absent from
revision state and every export, and (finding A) that the calc-sheets plan
already mirrors registry structure and is the natural carrier for an evidence
surface. Reusing `LedgerFilingSnapshot`'s fingerprint as the binding content
address means evidence and staleness stay consistent by construction. Placing the
record in the domain and the capture in the application preserves the hexagonal
boundary the snapshot already respects. Making the evidence typed (not a flat
dump) honours the calculation-grounding and no-silent-under-declaration
disciplines: a casilla without an explainable basis becomes structurally
impossible to file.

## Consequences

- **Gain:** every ledger-derived modelo revision becomes self-evidencing; the
  export is a legally-sound filing artefact carrying its own fact basis; "why is
  casilla X this value" is answerable offline from the artefact alone.
- **Gain:** staleness and evidence share one content address, so a drifted
  revision and a stale evidence bundle are the same signal.
- **Cost:** the `CalculationRevision` envelope grows; the projection must stay
  bounded and a roundtrip + payload-size test guards it. Redaction policy must be
  applied before evidence leaves the secure boundary.
- **Cost:** capture adds a second projection pass at verify time (bounded, O(n)
  over contributors, reusing the single catalogue load).
- **Pathway:** opens the export-parity workbook (the sibling ADR) to render the
  evidence surface, and the live-Google export to upload an evidence-complete
  workbook.
- **Pitfall:** evidence must never silently omit a contributor present in
  `source_transaction_ids`; the capture asserts the evidence set equals the
  fingerprint set.

## Codification candidates

- **Rule slug:** `ledger-derived-revisions-bundle-evidence`.
  **Rule:** Every modelo calculation revision that derives any casilla from the
  ledger must bundle the typed ledger evidence (contributing-row projections plus
  manual fact-basis entries) pegged to the revision's snapshot fingerprint, and
  every export of such a revision must carry that evidence or a resolvable
  in-system reference to it — an export with neither is refused.
