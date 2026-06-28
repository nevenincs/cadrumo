---
tags:
  - '#research'
  - '#modelo-123-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-modelo-130-calc-verify-adr]]'
  - '[[2026-04-27-modelo-115-calc-verify-adr]]'
---

# `modelo-123-calc-verify` research: 2024-2026 aggregation verification

Modelo 123 is a cross-tax IRPF / IS / IRNR withholding form for determined
capital-income rents. The implemented calc-verify surface is intentionally
aggregation-only: it verifies totals and the complementaria offset, not
individual per-row withholding-rate computation.

## Findings

The supported formula surface is stable across 2024, 2025, and 2026:
`03 = 01 + 02`, `06 = 04 + 05`, `09 = 07 + 08`, and `11 = 09 - 10`.
Inputs remain `01`, `02`, `04`, `05`, `07`, `08`, and `10`.

The 2026 ruleset is a structural clone of 2025 with `ruleset_id`
`modelo_123.2026`, a 2026 effective range, empty parameters, and the same
casillas, formulas, and legal citations as 2025. This mirrors the 2026
clone pattern used by Modelo 115 and Modelo 130 when the legal/computational
surface does not change.

Legal grounding is BOE primary-sourced. LIRPF art. 25 characterizes
rendimientos del capital mobiliario; LIRPF art. 101.4 fixes the ordinary
IRPF retention rate for capital income at 19%; RIRPF art. 90 applies 19%
to the capital-income withholding base. These sources explain the expected
IRPF worked-example amounts but do not turn Modelo 123 into a per-row rate
calculator because the form also covers IS and IRNR rents.

Extractor coverage can share one 11-casilla layout across 2024, 2025, and
2026. The synthetic generator path already supports per-year template
revision values, so the Kent CLI integration can render 2024/2025/2026
L3 PDFs and drive the real `parse_declaracion` plus `verify_declaracion`
flow.

L1 public-anchor coverage is waived. Modelo 123 filings expose internal
withholding relationships and payer/payee-sensitive data, and no public
hash-pinnable fixture is available for this Tier-L increment. L3 synthetic
round-trip coverage is the accepted verification path.

Primary sources:

- LIRPF Ley 35/2006, BOE-A-2006-20764, arts. 25 and 101.4:
  `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764&p=20260228&tn=1`
- RIRPF RD 439/2007, BOE-A-2007-6820, art. 90:
  `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820&p=20260228&tn=1`
