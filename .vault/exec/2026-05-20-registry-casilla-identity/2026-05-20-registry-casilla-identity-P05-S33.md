---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S33'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-04-28-modelo-200-calc-verify-adr]]'
---

# `registry-casilla-identity` `P05.S33`

Corrected the Modelo 200 page-14 cuota chain against the AEAT Manual
práctico de Sociedades 2024. The shipped registry formula
`modelo-200-cuota-ejercicio-a-ingresar-devolver` computed casilla 00599
as cuota líquida minus *pagos fraccionados* — a confirmed CRITICAL tax
defect. The manual (pages 500-501) requires cuota líquida minus
*retenciones e ingresos a cuenta*; pagos fraccionados subtract one step
later at 00611. This Step implements the manual-grounded chain recorded
in the "Amendment (2026-05-20)" section of
`2026-04-28-modelo-200-calc-verify-adr`.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/formulas.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/completeness-manifest.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-001.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0018-modelo-200-page-014b.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0549-liquidacion-iv-cuota-del-ejercicio-a-ingresar-o-a-devolver.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0557-liquidacion-iv-cuota-del-ejercicio-a-ingresar-o-a-devolver.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-01033-reserva-nivelacion-aumentos.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-01034-reserva-nivelacion-disminuciones.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-01330-base-imponible-postnivelacion.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00601-pago-fraccionado-1.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00603-pago-fraccionado-2.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00605-pago-fraccionado-3.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/tributacion-conjunta-00625-estado-porcentaje.toml`
- Modified: `src/aeat/domain/calculations/registry/_record_design.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
- Modified (out-of-scope blocker fix): five Modelo 202 export-layout fragments under
  `src/aeat/_data/registry/aeat/modelos/202/revisions/*/export_layouts/`

## Corrected and authored formulas

All four page-14 cuota-chain formulas were verified field-by-field
against the AEAT Manual práctico de Sociedades 2024 corpus
(`aeat-modelo-200-manual-2024`).

- `modelo-200-base-imponible-despues-reserva-nivelacion` →
  `DP200014:01330` = `(DP200014:00552 + DP200014:01033) -
  DP200014:01034`. Manual page 361, "casilla [01330] = [00552] +
  [01033] - [01034]". `legal_refs`: LIS art. 105 (reserva de
  nivelación) plus arts. 29/30/41.
- `modelo-200-cuota-integra` → `DP200014:00562` =
  `(DP200014:01330 x DP200014:00558) / 100`. Manual page 362,
  "[00562] = [01330] x [00558]/100". `legal_refs`: LIS arts. 30
  (cuota íntegra) and 29 (tipo de gravamen).
- `modelo-200-cuota-ejercicio-a-ingresar-devolver` (CORRECTED) →
  `DP200014B:00599` = `(DP200026:00625 / 100) x
  ((DP200014B:00592 - DP200014B:01766) - DP200014B:01784)`. Manual
  pages 500-501, "[00599] = ([00625]/100) x ([00592] - [01766] -
  [01784])". The prior shipped formula subtracted the
  `rel-202-pagos-fraccionados` relation from cuota líquida — the
  defect. `legal_refs`: LIS art. 41 (deducción de las retenciones,
  ingresos a cuenta y pagos fraccionados de la cuota líquida) plus
  arts. 29/30. The ADR amendment also cites LIS art. 128
  (obligation to withhold); art. 128 is **not** in the registry
  legal catalogue and adding an unreviewed catalogue entry would
  breach the grounding discipline, so the formula is grounded on
  art. 41 — the operative article that actually governs subtracting
  retenciones from the cuota líquida (its catalogued `required_text`
  is verbatim "Deducción de las retenciones, ingresos a cuenta…
  Serán deducibles de la cuota líquida"). Art. 128 is the
  *withholding obligation*, contextual rather than the computation
  rule. The misleading `source_citations.required_text` (formerly
  citing "pagos fraccionados") now quotes the manual's actual 00599
  section text.
- `modelo-200-cuota-diferencial` → `DP200014B:00611` =
  `DP200014B:00599 - (DP200014B:00601 + DP200014B:00603 +
  DP200014B:00605)`. Manual page 506, "[00611] = [00599] - ([00601]
  + [00603] + [00605])". `legal_refs`: LIS arts. 40 (pago
  fraccionado) and 41.

## Pagos-fraccionados relation move

The manual's literal 00611 formula subtracts the three pagos-
fraccionados casillas `00601 / 00603 / 00605` directly. Those
casillas are operator-input fields the contributor fills on page 14
bis (manual page 506: "se deben consignar en las siguientes
casillas"); their underlying amounts derive from the Modelo 202
quarterly instalments. The `modelo-200-2024-rel-202-pagos-
fraccionados` relation and its `modelo-200-2024-pagos-fraccionados-
anuales` binding remain declared on the foundation construct as the
cross-model M202 provenance, but the relation is no longer
referenced inside the 00599 formula expression — it belonged at the
00611 step, and the manual expresses that step as a direct subtraction
of the three input casillas rather than a relation aggregate.

## Segment-qualification decisions

Per the M200 Diseño de Registros corpus, each dependency casilla was
checked for cross-segment number collision:

- Segment-qualified (genuine multi-segment collision, mirroring the
  P04 `00552/00558/00562/00592/00599/00611` treatment): `00552`,
  `00558`, `00562`, `00592`, `00599`, `00611` (already qualified by
  P04); newly qualified `DP200014:01033`, `DP200014:01034`,
  `DP200014:01330` (each recurs in DP200014 + DP200020B/DP200024),
  `DP200014B:00601`, `DP200014B:00603`, `DP200014B:00605` (each
  recurs in DP200014B + ECPN/aseguradoras segments), and
  `DP200026:00625` (recurs in DP200011 + DP200026 + DP200042 — the
  Estado tributación-share casilla, page 26 per the manual note).
- `01766` and `01784` are unique to DP200014B in the Diseño and do
  not collide for reference-resolution purposes, so their formula
  operands are unambiguous. They were still declared with
  `segmento = "DP200014B"` because the calculation-completeness gate
  requires every manifest casilla to be declared at its
  `(segmento, number)` Diseño identity, and the manifest derivation
  pins them to DP200014B. Their casilla `id` was promoted to the
  segment-qualified form for consistency with the runtime, which
  resolves a formula `casilla` leaf by exact `id`.

Formula targets and operands use the canonical segment-qualified
`id` for every multi-segment casilla; segment-aware reference
resolution (P02) resolves every operand unambiguously, confirmed by
`build_snapshot` plus the formula runtime evaluating the chain
end-to-end.

## Diseño sheet-name hygiene fix

The M200 Diseño workbook carries a trailing space on two sheet tabs
(`DP200026 `, `DP200029 `). The record-segment sheet name is the
identity the completeness-manifest derivation matches against, so
`_extract_sheet_rows` now strips surrounding whitespace from the
sheet name. Without this, `DP200026:00625` dropped out of the
derived manifest. No code or registry data depended on the
space-suffixed names.

## Manifest regeneration

The M200 calculation-completeness manifest was regenerated with
`derive_calculation_completeness_casillas` against the corpus
Diseño. The closure grew from 2 casillas to 15 (the four formula
targets, every formula-expression operand, and the cuota-del-
ejercicio verification-expectation operand). The regenerated
manifest enumerates `DP200014: {00552, 01033, 01034, 01330, 00558,
00562}`, `DP200014B: {00592, 01766, 01784, 00599, 00601, 00603,
00605, 00611}`, and `DP200026: {00625}`. The off-load-path drift
re-verification test re-derives this exact set from the corpus and
matches; M200 clears the calculation-completeness gate.

## Calc-verify oracle

`test_modelo_200_page_14_cuota_chain_matches_aeat_manual_worked_example`
exercises the AEAT manual worked liquidación example
("Liquidación del IS 2024 sin tributación mínima", manual pages 399
and 401). Cuota líquida `00592 = 0`, retenciones `01766 = 20.000`,
Estado share `00625 = 100` give cuota del ejercicio `00599 =
-20.000`; pagos fraccionados `00601 = 10.000` give cuota diferencial
`00611 = -30.000`. Both `-20.000` and `-30.000` are AEAT-published
bold figures lifted verbatim from the manual table, not recomputed
from the registry formula — satisfying the
no-tautological-calculation-tests rule. A companion test asserts the
cuota íntegra chain (`01330 = 1.000.000`, `00562 = 250.000`) against
the same worked example (manual page 401).

## Out-of-scope blocker: Modelo 202 export-layout duplicate field ids

A concurrent "Registry hardening" campaign had committed truncated
export-layout field ids in five Modelo 202 fragments (field ids cut
to a fixed width, collapsing distinct `<AUX>`/`</AUX>` literals and
distinct header fields onto the same id), which broke
`load_registry_tree` for the whole registry and blocked every
verification gate for this Step. The truncated ids were
disambiguated by re-appending each field's `-pos-<offset>` suffix.
This is the minimum mechanical fix needed to unblock the
all-26-modelos gate; M202 export, parse, and committed-registry
tests pass after it.

## Tests

`pytest test_modelo_200_registry.py test_formula_runtime.py
test_referential_integrity.py test_modelo_parity_coverage.py
test_record_design.py` — 109 tests pass, including the two new
manual-oracle calc-verify tests, the manifest drift re-verification,
referential integrity, and all-26-modelos parity coverage.
`pytest test_modelo_202_registry.py test_export.py
test_committed_registry.py` — 75 tests pass, confirming the M202
blocker fix is clean. A `RegistryValidator` sweep over all modelos
confirms `ok=26 fail=0`. `ruff check` and `ruff format` are clean on
the touched Python files.
