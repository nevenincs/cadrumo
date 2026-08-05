---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:3cf39922c1316701b503fb4d6d5639509dfd28027a85acfcb8886c22861af688'
step_id: 'S13'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-invoice-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add the partial-invoice decomposition contract so an ungrounded record is excluded but visible rather than silently dropped and ## Scope

- `src/cadrumo/domain/transactions` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the partial-invoice decomposition contract so an ungrounded record is excluded but visible rather than silently dropped

## Scope

- `src/cadrumo/domain/transactions`

## Description

- Add `src/cadrumo/domain/invoices/_decomposition.py` carrying the contract: `InvoiceDecompositionDefect`, `InvoiceComponents`, `InvoiceDecomposition`, `InvoiceDecompositionPartition`, `decompose_invoice`, `partition_invoices`, and the per-defect operator guidance mapping.
- Classify rather than refuse: a partial record stays a valid `Invoice` and the verdict is data, so the document the operator must be told about is never deleted at construction.
- Decide grounding from the Axis-A component-expectation table in `domain/iva`, never from which fields happen to be populated.
- Enforce the mutual exclusion of components and defects on `InvoiceDecomposition`, and the identity `total = taxable_base + cuota` with `cash = total - retencion` on `InvoiceComponents` itself.
- Promote the seven symbols into the package `__all__` in `src/cadrumo/domain/invoices/__init__.py` in the same commit as the module, and describe the contract in the facade docstring.
- Regenerate the api stub for the new module.
- Add twenty behavioural cases in `src/cadrumo/domain/invoices/tests/test_decomposition.py`.

## Outcome

Landed as commit `ab37af1d11` (5 files, +730 lines, 0 deletions).

Raw counts, serial runs (`-n 0`): `test_decomposition.py` 20 passed; the whole `domain/invoices/tests` package 117 passed. `test_json_schema_conformance.py` 162 passed under `-m integration`. Tree-wide `pytest src/cadrumo --collect-only -q` collected 19930 of 23810 with no collection errors.

The step scope as written named `src/cadrumo/domain/transactions`; the contract governs the rich `Invoice` aggregate and landed in `src/cadrumo/domain/invoices` alongside it.

Four defects ship: undeclared IVA treatment, a missing base where the category requires one, a cuota contradicting a zero-by-law category, and an unresolved currency conversion. Defects accumulate rather than short-circuit, so one pass shows an operator everything wrong with a record.

No new surfacing channel was invented. The verdict is typed domain data with a remediation sentence per defect, ready for the existing envelope notice channel that the income side already uses; wiring it into the calculate path belongs to the consuming step, not this one.

## Notes

Three checks were deliberately not implemented, each because implementing it would have been wrong rather than merely harder. All three carry the reason inline.

A category whose Axis-A cuota is `REQUIRED` showing a zero cuota is not flagged. Those categories are precisely the ones where somebody other than the issuer settles the cuota, under inversion del sujeto pasivo or at customs, so a zero cuota is the correct face of the invoice; a zero-rated line produces one legitimately on a domestic rated category too.

An OSS or IOSS projected invoice is exempted from the cuota contradiction check. Its cuota is the destination member state's, settled through the special regime rather than the Spanish general cuota the Axis-A row describes. Without this carve-out the committed OSS union-scheme roundtrip fixture would be classified ungrounded. The underlying tension is real and is reported to the team lead rather than silently encoded: that fixture declares `INTRA_COMMUNITY_SUPPLY`, whose row is zero-by-law, while carrying a genuine destination-state cuota.

The retencion limb of the ADR's minimum grounded shape is not implemented. No shipped Axis-A row declares `IvaRetencionExpectation.EXPECTED`; every row is `POSSIBLE`, `NOT_EXPECTED` or `UNKNOWN`. A check keyed on `EXPECTED` would therefore be unreachable by data and untestable without fabricating a table row, which is worse than its absence. A declared retencion on a `NOT_EXPECTED` category is likewise not flagged, because that column's own documentation calls the value a default rather than a prohibition.

The `python -m dev.docs.apidocs scaffold` run regenerated four stubs belonging to peer campaigns (`domain.iva._components`, `domain.transactions._retencion_parameters`, `domain.calculations.registry._ledger_binding_resolution`, `application.modelo._review_package_keypair`) and touched a registry parent toctree that a peer had already staged. Only the two stubs for this Step were staged; the peer deltas were left in the working tree for their owners and no staged peer content was disturbed.
