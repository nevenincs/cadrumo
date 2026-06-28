---
tags:
  - '#reference'
  - '#modelo-123-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-modelo-123-calc-verify-research]]'
  - '[[2026-04-27-modelo-123-calc-verify-adr]]'
---

# modelo 123 2024-2026 rule delta

Modelo 123 introduces no computational delta across 2024, 2025, and 2026
for Kent's supported calc-verify surface. The implementation verifies the
declaration's aggregate rows and complementaria offset only.

## Casilla Inventory

| Casilla | Classification | Rule |
| :--- | :--- | :--- |
| `01` | user-supplied | Dividend recipients |
| `02` | user-supplied | Other capital-income recipients |
| `03` | computed | `01 + 02` |
| `04` | user-supplied | Dividend withholding base |
| `05` | user-supplied | Other capital-income withholding base |
| `06` | computed | `04 + 05` |
| `07` | user-supplied | Dividend withholdings |
| `08` | user-supplied | Other capital-income withholdings |
| `09` | computed | `07 + 08` |
| `10` | user-supplied | Prior result deducted in complementaria |
| `11` | computed | `09 - 10` |

## Year Delta

| Year | Ruleset | Effective Range | Numeric / Structural Delta |
| :--- | :--- | :--- | :--- |
| 2024 | `modelo_123.2024` | 2024-01-01 to 2024-12-31 | Structural clone of 2025 |
| 2025 | `modelo_123.2025` | 2025-01-01 to 2025-12-31 | Baseline aggregation ruleset |
| 2026 | `modelo_123.2026` | 2026-01-01 to 2026-12-31 | Structural clone of 2025 |

No M123 parameter table entries exist for these years. Per-row withholding
amounts remain declared inputs because Modelo 123 covers IRPF, IS, and IRNR.

## BOE Sources

- LIRPF Ley 35/2006, BOE-A-2006-20764, art. 25: characterizes capital-income
  rents such as dividends and interest.
- LIRPF Ley 35/2006, BOE-A-2006-20764, art. 101.4: ordinary IRPF retention
  and payment-on-account rate for capital income is 19%, subject to statutory
  exceptions.
- RIRPF RD 439/2007, BOE-A-2007-6820, art. 90: applies the 19% rate to the
  capital-income withholding base.

Current 2026 consolidated BOE URLs:

- `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764&p=20260228&tn=1`
- `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820&p=20260228&tn=1`

## L1 Anchor Decision

Waived for this issue. Modelo 123 filings expose internal withholding
relationships and payer/payee-sensitive data, and no public hash-pinnable
fixture is available. L3 synthetic generator round-trips provide the
verification evidence.

## Mutation Fingerprint

Each M123 year has one mutable `sub_op` node on casilla `11`; no percent-rate,
bracket-threshold, or scalar mul/div nodes are present on the supported
aggregation surface. The percent-rate mutation harness therefore has no M123
rate node to exercise, while operand-swap coverage exercises casilla `11` for
2024, 2025, and 2026.
