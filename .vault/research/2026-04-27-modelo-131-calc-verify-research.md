---
tags:
  - '#research'
  - '#modelo-131-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
---



# modelo-131-calc-verify research: calc-verify-roundtrip

## Findings

Modelo 131 is the quarterly IRPF payment form for taxpayers in estimación objetiva. The local implementation is casilla-level verification, not a full activity-code module calculator: it verifies the liquidación chain once the taxpayer or form has supplied the module-derived amounts.

The M130 reference pattern establishes the same shape needed here: annual ruleset files, non-overlapping effective windows, per-year worked examples, registry/list updates, mutation harness enumeration, a rule-delta reference, and citation-audit evidence.

Current M131 surface:

- `modelo_131_2024.py` and `modelo_131_2025.py` already exist.
- `modelo_131_v2025.py` extracts casillas 01 through 15, covering the full liquidación block.
- `TestKentImportsModelo131Declaracion` already contains the three mandatory import cases plus a discrepancy case.
- The synthetic PDF generator exists through the shared declaration fixture path used by the extractor and integration tests.

BOE source trail:

- RD 439/2007 art. 110 governs payment amount formulas: 2% is used for no-employee objective-estimation or no datos-base sales/income, and 2% is used for agricultural, livestock, forestry, and fishing income.
- Orden EHA/672/2007 approves Modelo 131.
- Orden HFP/1359/2023 develops the objective-estimation method for tax year 2024.
- Orden HAC/1425/2025 develops the 2026 objective-estimation method and states that 2026 keeps the 2025 module amounts and instructions.

Casilla classification:

- User-supplied: 01, 02, 03, 05, 08, 09, 11, 12, 14.
- Computed: 04, 06, 07, 10, 13, 15.
- Formula node distribution: two parameter-backed PercentFormula nodes and five SubFormula nodes; no BracketsFormula and no literal Mul/Div scalar nodes in the current casilla-level ruleset.

Risk notes:

- The issue text refers broadly to coefficient-by-activity module lookups, but the repository currently models Modelo 131 from the printed liquidación casillas. Extending to activity-code tables would be a deeper calculator feature and is out of scope for this implementation.
- L1 public-PDF anchoring is waived because public Modelo 131 filings are unlikely to be safely reusable; synthetic PDF round-trip plus CLI declaration import is the available test anchor.
