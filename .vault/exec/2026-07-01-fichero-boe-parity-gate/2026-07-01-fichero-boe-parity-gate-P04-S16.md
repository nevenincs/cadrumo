---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:c5d86f1f1b514da2771e4c9bb09e95076682f1b8651f6dbe3c97a636efe0ea58'
step_id: 'S16'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Assert rendered numbering, segmento and record order fidelity in the fichero-BOE parity test

## Scope

- `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`

## Description

- Extend `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py` with a parametrised parity lock asserting rendered numbering, segmento, and record-order fidelity hold for the real shipped structure of every export-capable covered modelo, and asserting the numbering check is non-vacuous by requiring at least one representable manifest casilla is cross-checked.
- Add anti-tautology drift cases proving each fidelity dimension bites: a mutated registry casilla number, a mutated registry segmento, a reversed record-order permutation, and collapsed duplicate emit orders each raise the hard `FilingExportError`.

## Outcome

- The fichero-BOE parity regression test now locks numbering, segmento, and record-order fidelity, not only casilla presence, and proves the gate is not vacuous and that every fidelity dimension fails on injected drift.
- The full parity file passes with 11 new assertions; the fichero-BOE parity, completeness gate, completeness sets, subview manifest, and export roundtrip suites together pass 50 tests, and the export-path suite spanning the modelo-level export orchestration passes 79 tests, with no regression from the subview projection or the gate-signature change.

## Notes

- The drift cases mutate the projected registry metadata and the export-layout record order directly, so the injected drift reproduces the exact structural divergence the gate exists to refuse rather than an artificial condition.
- A full parallel run of the filing and modelo suites surfaced 23 failures in unrelated file-flow, verify, iva-wallet, and cross-period-carry tests; each passes in isolation and when the files are re-run sequentially, confirming the known loader-cache race under parallel pytest rather than a regression from this change.
