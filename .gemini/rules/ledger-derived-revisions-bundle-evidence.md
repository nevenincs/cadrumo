---
name: ledger-derived-revisions-bundle-evidence
trigger: always_on
---

# Ledger-derived revisions bundle their evidence

## Rule

Every modelo calculation revision that derives any casilla from the ledger MUST
bundle the typed ledger evidence — the contributing-transaction projections plus
the manual fact-basis entries — pegged to the revision's snapshot fingerprint,
and every export of such a revision MUST carry that evidence (or a resolvable
in-system reference to it). An export of a ledger-derived revision that carries
neither is refused.

## Why

The `modelo-export-evidence-parity` research (finding B) found that revision
state stored only fingerprints (`LedgerFilingSnapshot`) — the fact basis that
explains *why a casilla holds its value* was absent from both the persisted
`CalculationRevision` and every export, so "why is casilla X this value" was
unanswerable from a filing artefact alone. A human files outside the
application; an artefact whose numbers cannot be re-derived from bundled
evidence is legally frail. The `2026-06-03-modelo-export-evidence-parity-adr`
decided that the typed evidence (signed amount, currency, direction,
base/IVA/rate/category, irpf category, EU member state, FX, lifecycle, business
proportion, legal_refs/source_refs, attachment/document-link ids per
contributor, plus operator manual entries) rides inside the encrypted revision
envelope bound by the same `snapshot_fingerprint`, so evidence and staleness
share one content address. This is the data-carrying companion to
[[aeat-calculation-grounding]] (provenance through boundaries) and
[[no-silent-under-declaration]] (a casilla without an explainable basis must not
file silently).

## How

- **Good:** `compute_ledger_filing_evidence` projects the resolved
  `source_transaction_ids` into typed `LedgerEvidenceRow`s plus
  `ManualFactBasisEntry`s, binds them to the snapshot fingerprint, and the
  `verify_modelo_revision` action captures it alongside the fingerprint snapshot
  in one catalogue load; the evidence persists inside the encrypted
  `CalculationRevision` and survives a strict save→load→equality roundtrip with
  every defaultable field populated non-default.
- **Good:** the capture asserts the evidence set covers the fingerprint set
  (`_assert_evidence_covers_snapshot`); a bundle that drops a contributor present
  in `source_transaction_ids` raises rather than silently omitting it.
- **Good:** offline xls and online Sheets exports both read the same bundled
  evidence and render an identical `Evidencia` surface, so the two transports are
  evidence-identical.
- **Bad:** persisting a ledger-derived revision with only the fingerprint
  snapshot and no typed evidence — the casilla becomes unexplainable and the
  export is not a self-contained filing artefact.
- **Bad:** letting an export of a ledger-derived revision proceed when neither
  the bundled evidence nor a resolvable reference is present.
- **Bad:** asserting the evidence roundtrip against numbers hand-computed from
  the same formula; the roundtrip must assert real reconstitution of the bundled
  rows.

## Source

ADR `2026-06-03-modelo-export-evidence-parity-adr` (accepted); research
`2026-06-03-modelo-export-evidence-parity-research`; plan
`2026-06-03-modelo-export-evidence-parity-plan` (W01). Promoted per the
[[vaultspec-codify]] discipline.
