---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:cdaddc867e114fea595b61bd9aa8335ae02c5441e01a5237f66b78c6bdff60c7'
step_id: 'S35'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Confirm the notificacion package facade exports the sancion parse entry point and its typed record for the application layer, and that the PDF-bytes-to-text step reuses the canonical extract_pages_text_from_bytes rather than introducing a second extractor, verified by the import hygiene gate and a check that no second pdfplumber call site is added

## Scope

- `src/cadrumo/adapters/inbound/notificacion/__init__.py`

## Description

- Confirm the package facade exports the parse entry point and its typed record.
- Confirm no consumer reaches a private module across the package boundary.
- Confirm the bytes-to-text step reuses the canonical extractor and adds no second one.

## Outcome

Delivered. The facade exports the parse entry point, the typed record and the error family; the sole consumer imports through it rather than a private path. The import hygiene scan reports no findings against this package, and the tree-wide magnitude counters show zero cross-package private imports needing facade promotion.

The extraction claim was confirmed by sweep rather than by assertion: there is no PDF text extraction call of any kind under the notificacion package, and the one call on this path is the canonical extractor invoked from the application service.

## Notes

The package shipped without API documentation stubs, so the reader was silently absent from the generated reference. That was an in-scope regression against the documentation rule, which requires the scaffold to run in the same change as a module-tree change. The stubs were regenerated and only those naming this package's modules were staged, leaving every other campaign's regenerated stubs to their owners.

One exception survives on a technicality worth recording: the singularity gate added for the amount-pattern Step reaches two private modules across package boundaries to assert object identity. The hygiene scanner detects the from-module-import-name form and not the from-package-import-module form, so no debt entry was required and none was added. The reach is genuine and necessary - object identity is the gate's whole point - but it is an undeclared exception surviving on a detector blind spot, and should be either declared or the detector widened.
