---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:38b6f47abb18556addcf762c83fee9792341054893f76a35475d3088ba8750fe'
related: []
---
## Scope

Review the M100/2021 Aragon manual worked-example tranche against the modelo-parity-rollup contract. The review covers the year-specific official evidence, the 2021 casilla/formula producer wiring, the real registry calculation, external-grounding enrollment, and preservation of the existing verification expectation surface.

## Findings

### year-specific-aragon-divergence | medium | 2021 autonomic outputs must not reuse 2024 values

The bundled AEAT Manual practico de Renta 2021 worked example is at `corpus/manuals/renta/2021/part1/source.pdf.extracted.md#L34681-L34721`. It gives base general 23,900, base ahorro 2,800, and minimum 5,550 for a taxpayer resident in Aragon. The year-specific outputs are 0528=2,667.75, 0529=2,787.25, 0532=2,140.50, 0533=2,232.25, 0545=2,406.50, and 0546=2,498.25; 0519 and 0520 are 5,550.00. The autonomic values differ materially from the 2024 figures 2,621.89, 2,094.64, and 2,360.64. The finding is resolved by a dedicated 2021 oracle and real-behavior test; no 2024 value or formula/profile surface was copied.

The source contains an OCR/footnote artifact before the printed 2,213.75 at the autonomic scale step. The downstream arithmetic and final printed totals establish 2,787.25, 2,232.25, and 2,498.25 without legal ambiguity.

### revision-local-manual-shape | medium | 2021 minimum components remain manual inputs

The 2021 schema declares 0511, 0512, and 0515-0518 without computed formulas. The scenario supplies 0511=5,550.00, 0512=5,550.00, and 0515-0518=0.00, plus 0102=23,900.00 and 0429=2,800.00. Neutral 2021 binding and relation inputs are supplied through the real calculation harness. This preserves the revision-local producer contract and avoids importing the later profile/formula chain.

### double-wired-cuota-chain | low | The eight grounded computed outputs are formula/casilla bidirectionally asserted

The 2021 casilla declarations and formula declarations are checked in both directions by the new real-behavior test. The mapping is: 0519 to `renta-2021-minimo-personal-y-familiar-estatal`; 0520 to `renta-2021-minimo-personal-y-familiar-autonomica`; 0528 to `renta-2021-cuota-escala-estatal-sobre-base-liquidable-general`; 0529 to `renta-2021-cuota-escala-autonomica-sobre-base-liquidable-general`; 0532 to `renta-2021-cuota-base-liquidable-general-estatal`; 0533 to `renta-2021-cuota-base-liquidable-general-autonomica`; 0545 to `renta-2021-cuota-integra-estatal`; and 0546 to `renta-2021-cuota-integra-autonomica`. Each casilla must be computed, point to its declared formula, and have that formula target the same casilla.

### external-grounding-enrollment | low | The eight official outputs are active verification evidence

`0002-reconcile-when-present.toml` now declares exactly 0519, 0520, 0528, 0529, 0532, 0533, 0545, and 0546 as externally grounded. The reconciliation list keeps all existing entries and adds only the missing six IDs: 0519, 0520, 0532, 0533, 0545, and 0546; 0528 and 0529 were already present. The 2021 coverage-gated contract remains unchanged. The enrollment test reads the validated policy fold and confirms every grounded output is both externally grounded and reconciled.

### sol-adjudication | low | The narrow execution contract was approved

SOL approved the additive three-file write set after RAG/code grounding: the manual oracle JSON, the real-behavior test, and the additive 2021 reconcile expectation edit. SOL required the exact year-specific values above, the manual input shape, formula mapping, Aragon-versus-Madrid anti-tautology behavior, no production formula/profile/binding/parameter changes, no mocks or copied business logic, and no changes to M100/2025 manual rows 0150, 0613, or 1481. The source and code evidence were sufficient; no legal or source blocker remained.

## Implementation

- `src/cadrumo/_data/corpus/manual_oracles/modelo-100-2021-cuotas-integras-escala-aragon.json` records the official locator, eight expected values, formula IDs, and source boundary.
- `src/cadrumo/domain/calculations/registry/tests/test_m100_2021_cuotas_integras_escala_aragon_manual_worked_example.py` runs the real registry scenario, checks the Aragon oracle, checks the Aragon/Madrid tariff divergence, asserts bidirectional formula wiring, and verifies live policy enrollment.
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/verification_expectations/0002-reconcile-when-present.toml` contains the additive external-grounding and reconciliation enrollment.

## Verification

The focused M100/2021 tranche passes 4 tests with `uv run --no-sync pytest -q -n 0`. Ruff format/check pass for the new test, and `git diff --check` is clean for the scoped files. The verification is real-behavior based and uses the validated bundled registry; it does not use fakes, mocks, patches, copied formulas, or tautological expected-value calculations.

No independent code-reviewer sign-off is claimed for this tranche. SOL approval is architecture/contract authorization, not an implementation review.

## Portfolio conformance boundary

The post-tranche portfolio check reports registry_validated=true, zero ratchet violations, zero grounding findings, 90 composed revisions, 73 composed modelos, 1,282 reconciled casillas, 77 declared grounding claims, and 26 bundled oracle payloads. It remains non-green only at the known locale boundary: audited locale leaves are 47,322 against the recorded 47,376 baseline and translated labels are 25,677 against 25,767. This tranche does not weaken or rewrite that baseline.

## Recommendations

Close the adjacent M100/2021 divergence finding as resolved and retain this oracle as the year-specific pattern. Continue the remaining portfolio waves separately: D2025 annual-layout evidence remains provisional and not yet measured, producer/legal/handoff coverage is not yet complete across all modelos, and the known locale ratchet boundary remains unchanged. Full modelo parity is therefore not claimed.
