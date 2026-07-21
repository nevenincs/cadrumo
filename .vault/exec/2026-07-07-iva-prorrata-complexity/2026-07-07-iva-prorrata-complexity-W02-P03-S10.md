---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Author the ley-37-1992 art-103 and art-106 legal entries with corpus_ref + required_text, grounded in the bundled consolidated LIVA

## Scope

- `src/aeat/_data/registry/aeat/legal/iva.toml`

## Description

- Author the new `[legal."ley-37-1992:art-103"]` entry (clases de prorrata / criterios de aplicacion) with `corpus_ref` into the bundled `ley-37-1992.html#a103` and a `required_text` cross-check covering the two-modalidad clause and the two art-103.Dos especial-applicability supuestos (the opt-in and the +10% obligation).
- Author the new `[legal."ley-37-1992:art-106"]` entry (la prorrata especial) with `corpus_ref` into `ley-37-1992.html#a106` and a `required_text` cross-check covering the three art-106.Uno reglas verbatim (100% exclusive-deductible, 0% exclusive-non-deductible, general-percentage common-use).
- Record the art-103.Dos.2 +10% obligation and the art-106 per-use routing in the entry notes for the especial mechanism.

## Outcome

- Modified files: `src/aeat/_data/registry/aeat/legal/iva.toml`.
- Both new entries pass the registry legal-grounding corpus cross-check (art-103 3 clauses, art-106 4 clauses); the legal-grounding gate is green (5 passed).
- Committed atomically with this exec record and the plan step check.

## Notes

- No new corpus file authored: art-103 and art-106 are already present verbatim in the bundled consolidated `ley-37-1992.html`, the same file both `corpus_ref`s point at.
- These entries ground the W02 especial mechanism: art-106 grounds the per-input 100/0/general routing (S11/S12), art-103.Dos.2 grounds the +10% mandatory-especial advisory (S13).
