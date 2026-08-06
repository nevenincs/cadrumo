---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:9ffd219dce03791e1a5e9ce759e465162d2ef9d55c9ff71b0e05cf1f27d1b502'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
---
## Scope

Review the SOL-authorized M100/2022 external-oracle enrollment tranche against the accepted five-domain parity contract. The review covered the 2022 manual worked example, the current formula/casilla reverse wiring, the real registry scenario, the external-grounding policy fold, and preservation of unrelated peer work in the reconciliation expectation.

## Findings

### 2022-manual-input-shape | medium | 2022 minimum inputs are manual and must not inherit the 2024 profile chain

The official 2022 worked example is grounded at `source.pdf.extracted.md` lines 37742-37785. In the 2022 registry, 0511 and 0512 are manual casillas, while 0519 and 0520 sum those inputs with the family components. The implementation supplies 0511=5550.00, 0512=5550.00, and neutral manual 0515-0518 values of zero; it does not copy the 2024 computed/profile path. This finding is resolved by the real scenario test.

### peer-safe-enrollment | low | Oracle enrollment preserves the pre-existing peer reconciliation additions

The pre-merge `0002-reconcile-when-present.toml` boundary contained only the peer additions 0224, 0529, and 0531, with SHA-256 `04D713826F26B55D222561CC804FDFBFF2B7E3E3A84F8BEDF7B219FEC2E9362D`. The tranche preserves those entries and adds the eight-value external-grounding declaration plus only the missing reconciliation IDs 0519, 0520, 0532, 0533, 0545, and 0546. No deletion or formula/schema change was made.

### scoped-tranche-clean | low | The authorized M100/2022 implementation has no open code-review findings

The scoped code review passed with no LOW, MEDIUM, HIGH, or CRITICAL implementation findings. The manual payload, 2022 legal/source provenance, reverse formula/casilla parity, anti-tautology check, and validated-policy enrollment were all confirmed. The focused tranche test passed 3 tests, the external-grounding integration gate passed 3 tests, and the reviewer reported 23 wiring/payload checks passed.

### adjacent-2021-revision-divergence | medium | M100/2021 AragÃ³n values are not interchangeable with 2024 values

The attempted 2021 packet was correctly held: the 2021 official manual and AragÃ³n parameter produce 0529=2787.25, 0533=2232.25, and 0546=2498.25, so the 2024 values 2621.89, 2094.64, and 2360.64 cannot be enrolled for 2021. No 2021 files were changed. A year-specific 2021 oracle remains an open campaign item.

### d2025-annual-coordinate | medium | D2025 remains provisional and not yet measured

The annual matrix still contains only the provisional M100/2025/0A/revision-2025 coordinate classified `not_yet_measured`. This is outside the completed 2022 tranche and remains the next five-domain wave: official annual-layout comparison, selector/producer evidence, legal handoff coverage, and independent behavioral verification.

### locale-ratchet-boundary | low | The known portfolio locale ratchet remains outside this tranche

`conformance audit --check` reports registry_validated=true and zero ratchet violations, but remains non-green because audited locale leaves and translated labels are below the recorded baseline. The tranche did not weaken or rewrite that baseline.

## Recommendations

Keep the 2022 manual-input shape as the revision-local oracle pattern. Do not clone values or fixture wiring across M100 years without re-reading the year-specific manual and parameters. Continue with a fresh SOL gate for the 2021 oracle using its actual AragÃ³n values, then execute the D2025 annual-layout and producer-evidence wave. Preserve the portfolio locale baseline until its own repair is grounded and reviewed.
