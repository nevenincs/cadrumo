---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S02'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W01.P01.S02` step record

Scope: `W01.P01.S02` - Verify-time evidence capture projection helper.

## Description

- Add `compute_ledger_filing_evidence` to project contributing ledger rows into typed evidence rows.
- Bind evidence bundles to the caller-supplied `snapshot_fingerprint`.
- Add `project_manual_fact_basis_entries` for operator casilla-input evidence projection.
- Carry manual fact-basis entries through the evidence bundle.
- Cover projection of tax facts, fingerprint binding, purchase-evidence id, attachment ids, duplicate contributor ids, and missing contributor ids.
- Cover blank manual-input omission.

## Outcome

The aggregation layer can now build a typed evidence bundle from a transaction catalogue using the same contributor identity surface as the filing snapshot helper.

## Notes

The helper deliberately mirrors `compute_ledger_filing_snapshot` by skipping contributor ids absent from the catalogue. The no-silent-omission guard remains tracked in S05.
