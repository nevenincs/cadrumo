---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-04-28-modelo-200-calc-verify-adr]]'
  - '[[2026-05-20-registry-casilla-identity-P05-S33]]'
---

# `registry-casilla-identity` Code Review

Review scope: the Modelo 200 page-14 cuota-chain correction Step
`P05.S33`, audited against the "Amendment (2026-05-20)" section of the
`modelo-200-calc-verify` ADR and the AEAT Manual práctico de Sociedades
2024 corpus.

## Status: PASS

No CRITICAL or HIGH findings. The change-set is safe to merge.

## Intent and correctness

INTENT-001 | PASS | Four cuota-chain formulas match the ADR amendment.
The authored expressions reproduce the manual-grounded chain
field-by-field: `01330 = (00552 + 01033) - 01034` (manual p.361),
`00562 = (01330 x 00558) / 100` (manual p.362),
`00599 = (00625 / 100) x ((00592 - 01766) - 01784)` (manual pp.500-501),
`00611 = 00599 - (00601 + 00603 + 00605)` (manual p.506). The formula
runtime evaluates the chain end-to-end against the AEAT manual worked
example to the published oracle values, confirmed by the two new
calc-verify tests.

INTENT-002 | PASS | The CRITICAL tax defect is corrected. The shipped
`modelo-200-cuota-ejercicio-a-ingresar-devolver` formula subtracted the
`modelo-200-2024-rel-202-pagos-fraccionados` relation (pagos
fraccionados) from cuota líquida. The corrected formula subtracts
retenciones e ingresos a cuenta (`01766`, `01784`) scaled by the Estado
share `00625`; the relation no longer appears in the 00599 expression.
The misleading `source_citations.required_text` no longer cites "pagos
fraccionados" and instead quotes the manual's actual 00599 retenciones
section.

INTENT-003 | PASS | Drift check: no extra logic beyond the ADR scope.
The pagos-fraccionados relation and binding remain declared on the
foundation construct as M202 cross-model provenance — correctly retained,
not deleted, since 00611's three input casillas derive from them.

## Calculation grounding

GROUND-001 | PASS | Every authored/corrected formula carries non-empty
`legal_refs` and `source_refs`. `source_citations.required_text` strings
were verified present in the normalised manual PDF corpus.

GROUND-002 | MEDIUM | LIS art. 128 (cited by the ADR amendment for
00599) was deliberately omitted. Article 128 is absent from the registry
legal catalogue; adding an unreviewed catalogue entry would breach the
calculation-grounding discipline. Formula 00599 is instead grounded on
LIS art. 41, whose catalogued `required_text` is verbatim "Deducción de
las retenciones, ingresos a cuenta… Serán deducibles de la cuota
líquida" — i.e. art. 41 is the operative article that governs subtracting
retenciones from the cuota líquida, the exact computation 00599 performs.
Art. 128 is the *withholding obligation*, contextual rather than the
computation rule. The substitution is sound and the executor recorded
the rationale in the Step record. Recommended follow-up: a future Step
may add a reviewed art. 128 catalogue entry and append it to the 00599
`legal_refs` for completeness against the ADR's literal article list.

## Segment-qualification

SEG-001 | PASS | Segment-qualification follows the P04 precedent.
Dependency casillas were checked against the M200 Diseño for genuine
cross-segment collision: `01033/01034/01330` (DP200014), `00601/00603/
00605` (DP200014B), and `00625` (DP200026) genuinely recur across record
segments and are segment-qualified. `01766/01784` are unique to
DP200014B; their casilla identity carries `segmento = "DP200014B"`
because the completeness gate requires every manifest casilla declared
at its Diseño `(segmento, number)` identity — a manifest-membership
requirement, not a reference-collision one. Formula targets and operands
use the canonical segment-qualified `id`; the runtime resolves every
operand unambiguously.

## Safety

SAFE-001 | PASS | No live AEAT write surface introduced. The change-set
is registry data plus an off-load-path extraction-tool hygiene fix.

SAFE-002 | PASS | The sheet-name `strip()` in `_extract_sheet_rows` is
safe and correctly scoped: it is the single chokepoint both workbook
extraction paths feed, no code or registry data depended on the
space-suffixed AEAT workbook sheet names (`DP200026 `, `DP200029 `), and
the off-load-path tool never runs on the snapshot-build hot path.

SAFE-003 | PASS | The two new calc-verify tests are non-tautological.
Expected values (`00599 = -20.000`, `00611 = -30.000`, `01330 =
1.000.000`, `00562 = 250.000`) are AEAT-published figures lifted verbatim
from the manual worked example (pages 399/401), not recomputed by the
test author from the registry formula. No mocks, skips, xfail, or stubs.

## Tests and gates

TEST-001 | PASS | `pytest` on the four mandated suites
(`test_modelo_200_registry`, `test_formula_runtime`,
`test_referential_integrity`, `test_modelo_parity_coverage`) plus
`test_record_design` — all green. The calculation-completeness manifest
was regenerated and the off-load-path drift re-verification re-derives
the identical 15-casilla set. All 26 modelos load valid. `ruff check` and
`ruff format` are clean on the touched Python files.
