---
tags:
  - '#research'
  - '#modelo-multiyear-renta-income'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
---



# `modelo-multiyear-renta-income` research: `income-tax prior-year cross-renta binding hooks (M200 BIN / M100 / M202)`

This research grounds the prior-year cross-renta binding hooks for three income-tax
modelos — Modelo 200 (BIN compensation), Modelo 100 (savings-base loss carryforward), and
Modelo 202 (instalment modality art.40.2) — for the multi-year-renta authorization gate
campaign. The goal is to confirm that each modelo's >=2-renta enrollment can be expressed
by re-using the proven Modelo 130 previous-filing binding shape plus formulas built from
the existing operator set, with zero new resolver code, and to surface every legal-grounding
gap honestly rather than paper over it. All findings below were verified against the in-repo
corpus and registry (RAG for discovery, `rg` and direct file reads for verification).

## Findings

### Proven binding template (Modelo 130) — the shape every hook re-uses

`src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0002-bindings.toml`
declares a `source = "previous_filing"` binding with a selector of the form
`{ source_modelo, filing_year_delta, period, source_casillas }` plus
`aggregation = { op = "sum" }`, `legal_refs`, `source_refs`, and a `source_citations`
block carrying `required_text` anchors. The resolver already consumes this shape
(`_binding_prefill.py`, `_bindings.py`): the expected source year is computed as
`filing_year + filing_year_delta + period_year_delta`. The `FormulaOperator` set
(`_schema.py`) already includes `add / subtract / multiply / percent / min / max / clamp /
if_then_else / sum / copy` plus comparison operators. Conclusion: all three income hooks are
registry-authoring + formula work; **no resolver code is needed**.

### M200 — BIN compensation cross-year (highest value, fully grounded)

Legal anchor confirmed in `src/aeat/_data/registry/aeat/legal/is.toml`: the
`ley-27-2014:art-26` entry (reviewed, `reviewed_by = "wgergely"`) carries `corpus_ref`
`corpus/normatives/html/ley-27-2014-art-26.html#a26`, the `notes` describing the 70%
limit, the €1M absolute floor, and the 10-year prescription, and `required_text` anchors
`"Compensación de bases imponibles negativas"`, `"70 por ciento de la base imponible
previa"`, `"1 millón de euros"`. An AEAT worked manual exists (`aeat-modelo-200-manual-2024`),
so the cap calculation is groundable and non-tautological.

- Carry seed casilla `00671` ("Detalle compensación BIN — TOTAL — Pendiente de aplicación
  en períodos futuros"); `00670` is pendiente-a-principio. Both are `input_kind = manual`
  today.
- Base imponible casilla pinned (verified): `DP200014:00552`
  (`semantic_role = is_liquidacion_iii_base_imponible`, `intentional_singleton`,
  `input_kind = manual`), whose `legal_refs` ALREADY include `ley-27-2014:art-25` and
  `ley-27-2014:art-26`. It is the exact casilla guarded by the existing ADVISORY predicate
  `modelo-200-base-imponible-determinada-cuando-resultado-positivo`
  (`implies_nonzero(["00501", "DP200014:00552"])`, `finding_kind = "ADVISORY"`) in
  `verification_expectations/0001-verification_predicates.toml`, which the
  `modelo-200-base-determination` ADR tracks for a Phase-2 derivation.
- Decision: pick option (b) — keep `00552` manual and add a computed consistency check that
  upgrades that advisory along the no-silent-under-declaration advisory→`BLOCKING_RULE` path:
  `00552 == base_previa − min(bin_disponible, max(literal(1000000), percent(70, base_previa)))`.
  `00501` and the per-origin-year BIN detail boxes (0174-0182, 00489/00504/.../00700) stay
  manual.
- Binding (home: `modelos/200/revisions/2024-y-siguientes/`): `source = "previous_filing"`,
  selector `{ source_modelo = "200", filing_year_delta = -1, period = "0A", source_output =
  "00671" }`, `aggregation = { op = "copy" }`, `legal_refs = ["ley-27-2014:art-26"]`. A
  single prior year satisfies the >=2-renta hook; the unlimited carry self-accumulates
  through `00671` year over year, so the design must NOT fan out into a multi-year
  selector.
- Cap formula (compensación aplicada): `if_then_else(greater_equal(base_previa, 0),
  min(bin_disponible, max(literal(1000000), percent(70, base_previa))), literal(0))`. This
  grounds both the €1M floor and the 70% ceiling and is the only genuinely-new formula
  logic in the whole A4 set.
- Honest flag (not blocking): the art.26.1 quitas/esperas and extinción exclusions are not
  modelled. Surface as an ADVISORY note plus a profile flag per the no-silent-under-declaration
  discipline, not a hard refusal.

### M100 — savings-base loss carryforward (grounded at summary strength; flag resolved)

Legal anchor: `ley-35-2006:art-49` in `src/aeat/_data/registry/aeat/legal/irpf.toml`
(reviewed), `corpus_ref` `corpus/normatives/ley-35-2006.json#art-49`, `notes` binding it to
the savings base and casillas 0429-0460, `required_text` anchors `"integración y
compensación"`, `"base imponible del ahorro"`, `"saldos negativos"`.

Honesty flag from the scratch research — "the JSON must be confirmed to carry the 4-year
period; the shipped HTML is preámbulo only" — was investigated and is **partially resolved**:

- The shipped `ley-35-2006.json` is a structured document with 40 article entries keyed by
  `numero`. Article 49 is present with `numero`, `permalink`, multilingual `titulo`, and a
  multilingual `summary`. There is **no verbatim BOE article body** in the JSON.
- The 4-year carry IS grounded, but in the `summary.es` field, which reads: "… así como la
  compensación en los cuatro años siguientes de los saldos negativos no aplicados, con un
  límite del 25 por ciento del importe del saldo positivo de la otra clase de renta." The
  English summary corroborates "the four-year carry-forward of unused negative balances,
  capped at 25 per cent".
- So the period is confirmed in-repo at **AEAT/editorial summary strength**, not verbatim
  statute. The `#art-49` fragment resolves conceptually (article 49 keyed by `numero`)
  although there is no literal `art-49` string anchor in the JSON. Residual gap for the
  plan: ingest the verbatim art.48/49 body to lift the grounding from summary to statute
  before any per-casilla numeric oracle is asserted.
- Bindings on the three carryforward casillas (0462→0393, 0465→0396, 1390→1391), each a
  `copy` of the prior-year generated saldo: selector `{ source_modelo = "100",
  filing_year_delta = -1, period = "0A", source_output = <prior saldo casilla> }`,
  `aggregation = { op = "copy" }`, `legal_refs = ["ley-35-2006:art-49"]`. No cap formula
  (straight copy + integración subtract). The 4-year expiry is modelled as a chain of
  single-year copies; an explicit year-tagged expiry guard is Phase-2 (higher effort).
- Oracle: structure / wiring only — there is no per-casilla workbook for the saldo box, so
  per the no-tautological-calculation-tests rule the E2E asserts wiring and provenance, not
  an author-invented Decimal.

### M202 — instalment modality art.40.2 (grounded; 1P year-offset flag confirmed real)

Legal anchor: `ley-27-2014:art-40` in `is.toml` (`art-40` and `art-40-3` entries both
present, `corpus_ref` `corpus/normatives/html/ley-27-2014-art-40.html#a40`). The
modalidad-40.2-vs-40.3 split is grounded in the AEAT instrucciones
`corpus/aeat_official/instructions/modelo_202/files/modelo-202-instrucciones.html`:
art.40.2 (clave 01) is the default for entities not obligated to 40.3 (INCN < 6M).

The instrucciones confirm the 40.2 base verbatim: "… como base del pago fraccionado la
cuota íntegra del último período impositivo cuyo plazo reglamentario de declaración
estuviese vencido el día 1 del mes que corresponda, … minorado en las deducciones y
bonificaciones …". They also confirm the instalment calendar: 1/P is the first 20 days of
April, 2/P October, 3/P December.

Honesty flag from scratch — "1P may need `filing_year_delta = -2`, not -1" — was investigated
and is **confirmed real**. Because the 40.2 base is the cuota of the last período whose
filing deadline was already vencido on the 1st of the payment month, and the prior-year
M200 is not due until July:

- **1/P (April):** on April 1st the most recent vencido M200 is two years prior (e.g. 1P
  paid April 2024 binds FY2022's M200, filed July 2023; FY2023's M200 is not due until July
  2024). So 1/P requires `filing_year_delta = -2`.
- **2/P (October) and 3/P (December):** the prior-year M200 (filed July) is already vencido,
  so these require `filing_year_delta = -1`.

- Casillas pinned (verified): only `01` ("Mod.40.2 base", `required = true`, `input_kind =
  manual`) flips manual → prior-year-bound. `03` ("Mod.40.2 a ingresar") is ALREADY computed
  by formula `modelo-202-modalidad-40-2-a-ingresar` =
  `subtract(percent(01, is.modalidad_cuota.percentage), 02)`; the 18% rate is the existing
  parameter `is.modalidad_cuota.percentage` (value `18`, `valid_from 2025-01-01`). So NO new
  formula — feeding `01` is sufficient and `03` recomputes.
- Binding (home: `modelos/202/revisions/2025-y-siguientes/`) populating `01`:
  `id = "modelo-202-2025-cuota-base-ejercicio-anterior"`, selector `{ source_modelo = "200",
  filing_year_delta = <-2 for 1P / -1 for 2P,3P>, period = "0A", source_output =
  <prior cuota-líquida casilla> }`, `aggregation = { op = "copy" }`, `legal_refs =
  ["ley-27-2014:art-40"]`. The per-period delta is the design subtlety the plan must encode.
- Modality gate inherited (verified): `derive_modelo_202_modality` is driven by the existing
  binding `modelo-202-2025-y-siguientes-incn-prior-12-months` (selector `{ profile_model =
  "taxpayer", field = "incn_prior_12_months" }`). For INCN > €6M, 40.2 is not offered (only
  40.3 clave 32), so the `01` binding must not populate for a 40.3-mandatory entity.
- Oracle: same-year 202→200 roll-up reconciliation plus the cross-year base binding;
  groundable against the instrucciones.

### Cross-cutting conclusions

- All three hooks re-use the M130 selector shape and the existing resolver → registry TOML +
  formulas only, zero resolver code.
- The only genuinely-new formula logic is the M200 €1M-floor / 70%-ceiling cap
  (`min / max / percent / if_then_else`).
- Two honest gaps to carry into the plan, not paper over: (a) M100 art.49 4-year period is
  grounded only at summary strength — ingest the verbatim statute body before any numeric
  oracle; (b) M202 1/P year-offset is `-2` (confirmed), so the per-period delta must be
  encoded explicitly rather than assumed `-1` across the board.
- Cross-renta primitives are already tested at both layers — domain
  `src/aeat/domain/calculations/registry/test_modelo_130_registry.py` and application
  `test_modelo_130_carry_forward_continuity.py` — so each enrollment E2E mirrors both layers
  by cloning the M130 continuity tests.
