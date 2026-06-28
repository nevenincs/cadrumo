---
tags:
  - '#audit'
  - '#p2e-tax-category-catalogue'
date: '2026-04-13'
modified: '2026-04-13'
related:
  - '[[2026-04-13-p2e-tax-category-catalogue-research]]'
  - '[[2026-04-13-p2e-tax-category-catalogue-adr]]'
  - '[[2026-04-13-p2e-tax-category-catalogue-plan]]'
---

# `p2e-tax-category-catalogue` Code Review

P2E-TAX-CATEGORY-CATALOGUE-001 | MEDIUM | Rule semantics tightened after reviewer pass
The initial registry encoded amortizable assets as `fixed_percentage=1.00`, encoded several vehicle categories with a default `0.50` ratio, and stored the health-insurance annual cap in a per-day field. The implementation was corrected in `_registry.py` and a regression check was added in `test_registry.py`.

P2E-TAX-CATEGORY-CATALOGUE-002 | LOW | Incomplete `MODELO_303` coverage kept as an explicit design decision
Review raised that some profiles do not carry `MODELO_303` mappings. This branch keeps `303` mappings only where the current-main public VAT surface can be represented honestly; forcing VAT-exempt or non-VAT categories into `303` would fabricate behavior that the committed corpus does not support.

P2E-TAX-CATEGORY-CATALOGUE-003 | LOW | Manual loader remains a readiness gate in phase 1
`load_category_profiles_from_manual()` currently uses `aeat.domain.manuals` as an availability check and then returns the curated registry. This is intentional for the phase-1 taxonomy substrate because the structured manual corpus does not yet expose category-profile extraction. The public API stays stable and later corpus-backed derivation can replace the fallback without changing downstream callers.

P2E-TAX-CATEGORY-CATALOGUE-004 | INFO | Final review status
No open code defects remain after the corrective registry patch. Final verification on the reviewed tree: `just lint`, `just typecheck`, `just test`, and `just hooks` all passed.
