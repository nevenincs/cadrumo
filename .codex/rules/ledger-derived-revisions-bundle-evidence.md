---
name: ledger-derived-revisions-bundle-evidence
trigger: always_on
---

# Ledger-derived revisions bundle their evidence

## Rule

Every modelo calculation revision that derives any casilla from the ledger MUST
bundle the typed ledger evidence — the contributing-transaction projections plus the
manual fact-basis entries — pegged to the revision's snapshot fingerprint, and every
export of such a revision MUST carry that evidence (or a resolvable in-system
reference to it). An export of a ledger-derived revision that carries neither is
refused.

## Why

`modelo-export-evidence-parity` research (finding B) found revision state stored only
fingerprints (`LedgerFilingSnapshot`); the fact basis explaining *why a casilla holds
its value* was absent from the persisted `CalculationRevision` and every export, so a
filing artefact was legally frail (a human files outside the app; unre-derivable
numbers cannot be defended). `2026-06-03-modelo-export-evidence-parity-adr` decided
the typed evidence (signed amount, currency, direction, base/IVA/rate/category, irpf
category, EU member state, FX, lifecycle, business proportion, legal_refs/source_refs,
attachment/document-link ids per contributor, plus operator manual entries) rides
inside the encrypted revision envelope bound by the same `snapshot_fingerprint`.
Companion to [[aeat-calculation-grounding]] and [[no-silent-under-declaration]].

## How

- **Good:** `compute_ledger_filing_evidence` projects resolved
  `source_transaction_ids` into typed `LedgerEvidenceRow`s plus `ManualFactBasisEntry`s
  bound to the fingerprint; `verify_modelo_revision` captures it in one catalogue load,
  persists it inside the encrypted `CalculationRevision`, and survives a strict
  save→load→equality roundtrip with every defaultable field populated non-default.
  `_assert_evidence_covers_snapshot` makes a bundle that drops a contributor present in
  `source_transaction_ids` raise, and offline xls and online Sheets exports read the
  same evidence to render an identical `Evidencia` surface.
- **Bad:** persisting a ledger-derived revision with only the fingerprint snapshot and
  no typed evidence (the casilla becomes unexplainable); letting an export proceed with
  neither bundled evidence nor a resolvable reference; or asserting the evidence
  roundtrip against numbers hand-computed from the same formula instead of real
  reconstitution of the bundled rows.

## Source

ADR `2026-06-03-modelo-export-evidence-parity-adr` (accepted); research and plan
(W01) of the same feature.
