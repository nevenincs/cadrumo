---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:d3f90c955d2f32cfa2faa75a46a95b3b26a61bd227eb5e2c9420660ba1162406'
related:
  - "[[2026-11-01-export-parity-suffered-withholding-schemas-adr]]"
  - "[[2026-06-15-art20-trabajo-reduccion-compute-adr]]"
  - "[[2026-07-01-modelo-100-trabajo-casilla-compute-adr]]"
  - '[[2026-11-01-export-parity-suffered-withholding-schemas-reference]]'
  - '[[2026-06-15-art20-trabajo-reduccion-compute-research]]'
  - '[[2026-07-01-modelo-100-trabajo-casilla-compute-research]]'
  - '[[2026-09-27-export-parity-renta-withholding-sources-adr]]'
  - '[[2026-11-11-export-parity-work-income-sourcing-research]]'
---
# `export-parity` adr: `Modelo 100 work income from the suffered-withholding payer record` | (**status:** `accepted`)

This record proposes an amendment to the accepted `2026-11-01-export-parity-suffered-withholding-schemas-adr`, which left income casillas to "a later decision" (its section 1, validator bullets) and kept the income quantities for them. It also proposes reconciling edits to the accepted `2026-06-15-art20-trabajo-reduccion-compute-adr` and `2026-07-01-modelo-100-trabajo-casilla-compute-adr`. Every accepted body stays unchanged until the operator or the coordinator authorizes this proposal. The wording to apply then is under "Proposed wording for the accepted records".

## Problem Statement

Modelo 100 calculates work income (rendimientos del trabajo, casillas 0003 to 0025) as zero for every taxpayer. The suffered-withholding payer record already holds the certificate's gross and in-kind figures (`src/cadrumo/domain/renta/retencion_soportada.py:68-72`). No binding reads them into an income casilla. The provider validator admits no income role, because `RETENCION_SOPORTADA_NON_CREDIT_ROLES` is empty for every class (`src/cadrumo/domain/calculations/registry/retencion_soportada_bindings.py:94-101`), so any quantity other than `pago_a_cuenta` is refused wherever it is bound (`:221-237`). The record has no field for the employee's Social Security contributions, so casilla 0013 has no source. Casilla 0019 is computed with a literal 2000 (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/formulas/0001-declarations.toml:17-22`). Casilla 0023, the art. 20 reduction, is a bare input that no formula targets. The personas `asalariada-familia` and `arrendador-jubilado` therefore calculate with zero work income (`dev/fixtures/personas/asalariada-familia/expectations.toml:31-46`, `dev/fixtures/personas/arrendador-jubilado/expectations.toml:40-51`).

## Considerations

- The payer certificate is the evidence (RIRPF art. 108.3), and the record is its typed copy. The payer's annual return design states, per perceptor, the dinerario gross, the valuation in kind, the ingresos a cuenta efectuados and repercutidos, the art. 18.2 and 18.3 reductions the payer applied, and the art. 19.2 a), b) and c) deductible expenses (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_190/files/04-190-orden-eha-3127-2009-de-10-de-noviembre-ac.pdf.extracted.md:1794-1840`). It states no employer pension or dependency-insurance contribution, no patrimonio protegido contribution, and no sindicato, colegio or legal-defence expense.
- Casilla 0013 is the art. 19.2 a), b) and c) total, the same scope as the payer's "gastos deducibles" field.
- Art. 19.2.f fixes 2.000 euros for every taxpayer with work income, increments it for geographic mobility and for active workers with a disability, and limits the whole to the gross after the other expenses (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:326-329`). The amounts apply once per declaration in joint filing (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:10888-10890`).
- Art. 20 measures the rendimiento neto before the 19.2.f expenses, that is after letters a) to e) only (`ley-35-2006.html.extracted.md:338`; every manual edition repeats it). The reduction requires that the taxpayer's "rentas, excluidas las exentas, distintas de las del trabajo" do not exceed 6.500 euros (`ley-35-2006.html.extracted.md:334`). The manual defines those rentas as the algebraic sum of net capital, activity, imputed and capital-gain income, before reductions and without integration or compensation rules (2025 manual md:11121-11126). The resulting balance may not be negative (`ley-35-2006.html.extracted.md:339`).
- The art. 20 amounts changed by edition, as each manual's table prints them: 5.565, 13.115, 16.825 and slope 1,5 (2022 manual md:8581-8590); 6.498, 14.047,5, 19.747,5 and slope 1,14 (2023 manual md:10476-10484); 7.302, 14.852, 17.673,52, 2.364,34, slopes 1,75 and 1,14, ceiling 19.747,5 (2024 manual md:10866-10875; 2025 manual md:11102-11117; LIRPF text `ley-35-2006.html.extracted.md:334-337`, effective 2024-01-01 under RDL 4/2024 art. 3.1).
- The accepted art. 20 record names casilla 0022 as the rendimiento neto of the schedule. That contradicts the law and every manual example: the 2024 example applies 7.302 at a rendimiento neto previo of 13.640 while the rendimiento neto is 8.140 (2024 manual md:11120-11131).
- The coordinator principle of 2026-11-11 23:25 binds: an item the application does not compute is a blocking finding when leaving it out could lower the tax, and may be a served non-blocking limitation only when leaving it out can only raise the tax and no stored fact shows it applies.
- The existing applicability rule reads the profile's declared income categories; class `trabajo` covers `trabajo` and `pension` (`src/cadrumo/domain/renta/retencion_soportada_applicability.py:64`). An absence attestation states that no payer withheld on income that existed (`src/cadrumo/domain/renta/retencion_soportada_absence.py:1-11`). It says nothing about the amount of that income.
- Supported years, projection and deltas follow the tax calculation domain rule's "Supported years, projection and registry deltas": no year in a key, dated values resolved through the registry, deltas only where the official text differs.

## Considered options

- Bind the record's quantities to the income casillas through the existing provider, extend the record with the certificate's missing figures, and compute 0019, 0022, 0023 and 0025 from dated parameters. Chosen.
- Leave 0003 to 0016 as operator inputs typed on the return. Rejected: it creates a second source beside the record, and a typed total cannot be reconciled per payer.
- Add a separate work-income record family. Rejected: it duplicates the payer identity, evidence fingerprint and class the suffered-withholding record already holds, and splits one certificate into two stores.
- Source 0003 to 0013 from the borrador or datos fiscales. Rejected: the accepted record keeps the informative borrador out of the precedence tier for this family, and datos fiscales is a later cross-check.
- Keep art. 20 advisory until a general "other income" resolver exists. Rejected: the other income is the sum of casillas the same calculation already produces, so one internal computed node covers it.

## Constraints

- Obligations. One source per figure: each certificate figure comes from the trabajo payer records and from no other binding, override, borrador tier or typed total. A casilla bound to the family is locked on the return and corrected only at the record.
- One mechanism for every supported year. No binding, parameter, formula, casilla or finding id carries a year. Amounts are dated parameter values resolved through the registry's dated selection and `revision_temporal_resolution`; a year without its own edition is projected and never promoted in grade.
- Every figure the law fixes for all workers is computed from a dated, cited registry parameter. No Python constant or formula literal holds a legal amount.
- The credit-set derivation, the `pago_a_cuenta` rules and the 0596 binding stay as accepted.
- Registry declarations of this decision live in their own numbered fragment in each Modelo 100 family directory they touch, at the family's storage baseline: the edition that declares `renta-retencion-soportada-trabajo` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:203`). The fragment number is agreed in one exchange with CALC-RENTA before the first registry edit. Later editions inherit them; an edition adds a delta only where its official table differs.
- Names, tokens and payload fields below are binding once accepted. Placements and helper names marked "hypothesis" may change within the boundary rules.

## Implementation

We will source Modelo 100 work income from the suffered-withholding records of class `trabajo` in every supported edition, add the two certificate figures the record lacks, and compute the art. 19.2.f expense and the art. 20 reduction from dated registry parameters.

### 1. Per-casilla sourcing (by semantic role)

| Casilla | Semantic role | Source | Omitted or unstated |
| --- | --- | --- | --- |
| 0003 | `irpf_rendimiento_trabajo_importe_integro_dinerario` | record quantity `importe_integro_dinerario` | missing record blocks |
| 0004 | `irpf_rendimiento_trabajo_especie_valoracion` | record quantity `valoracion_especie` | missing record blocks |
| 0005 | `irpf_rendimiento_trabajo_especie_ingreso_cuenta` | record quantity `ingreso_a_cuenta` | missing record blocks |
| 0006 | `irpf_rendimiento_trabajo_especie_ingreso_cuenta_repercutido` | record quantity `ingreso_a_cuenta_repercutido` | missing record blocks |
| 0007, 0012, 0017, 0018 | unchanged roles | unchanged formulas | - |
| 0008, 0009, 0010, 0024 | contribution and imputed-income roles | operator-stated on the return | blocking until stated |
| 0011 | `irpf_rendimiento_trabajo_reduccion` | record quantity `reducciones_aplicables` | missing record blocks |
| 0013 | `irpf_rendimiento_trabajo_gasto_ss_mutualidad` | record quantity `gastos_deducibles` | missing record blocks |
| 0014, 0015, 0016 | sindicato, colegio, defensa jurídica roles | operator-stated on the return | served non-blocking limitation |
| 0019 | `irpf_rendimiento_trabajo_gasto_otros` | computed: min(parameter, max(0, 0018)) | - |
| 0020 | `irpf_rendimiento_trabajo_incremento_traslado_residencia` | operator-stated on the return | served non-blocking limitation |
| 0021 | `irpf_rendimiento_trabajo_incremento_discapacitado_activo` | operator-stated on the return | blocking when the profile states a taxpayer disability, else served limitation |
| 0022 | `irpf_rendimiento_trabajo_rendimiento_neto` | computed: max(0, 0018 - 0019 - 0020 - 0021) | - |
| 0023 | `irpf_rendimiento_trabajo_reduccion_gastos_generales` | computed from the art. 20 schedule (section 4) | - |
| 0025 | `irpf_rendimiento_trabajo_rendimiento_neto_reducido` | unchanged formula 0022 - 0023, now never negative | - |

- Several payers sum: each binding is the `sum` over every trabajo record of the ejercicio.
- 0008, 0009, 0010 and 0024 are income, so leaving them out could lower the tax. No bundled payer design states them. They are operator-stated through the existing scalar override (`SET_OVERRIDE_VALUE`); an explicit zero states them. Verification raises the blocking finding `trabajo_income_unstated` for each one without an override on a return whose trabajo class is recorded. The finding names the casilla by role and serves its words.
- 0014, 0015, 0016 and 0020 are deductions that only the taxpayer can evidence, and no stored fact shows they apply. Leaving them out can only raise the tax. Verification and the export result serve the limitation `trabajo_deduction_not_computed` on every return with work income: it names the boxes by role and says the return may overstate the tax.
- 0021 is a deduction, but `renta_taxpayer.disability_grade` (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1530`) is a stored fact that can show it applies. When that fact states a disability and 0021 has no override, the finding is blocking; an explicit zero resolves it for a taxpayer who is not an active worker. The amount stays operator-stated because the record does not say which income is active work (pensions are also class `trabajo`).
- A stated 0015 above the RIRPF art. 10 limit or a stated 0016 above the art. 19.2.e limit is a blocking finding `trabajo_expense_above_limit`, read against the dated parameters of section 4.

### 2. Record schema (payload v2)

- `RetencionSoportadaRecord` gains `reducciones_aplicables` and `gastos_deducibles`, each the module's `_Importe` money type or `None`. They are read from the same certificate as the record's other figures, under the same `origin` and `evidence_fingerprint`.
- For class `trabajo` both fields are required at payload v2; an explicit 0.00 is the certificate's statement of none. For every other class both must be `None`.
- `RetencionSoportadaCantidad` gains `importe_integro_dinerario`, `valoracion_especie`, `reducciones_aplicables` and `gastos_deducibles`, each returning its field from `RetencionSoportadaRecord.quantity`. The combined `importe_integro` stays, as a cross-check quantity with no income role.
- The namespace `schema_version` becomes 2. The key grammar and identity are unchanged. A v1 payload parses with both new fields `None`.
- The record request (`src/cadrumo/application/retencion_soportada_certificado/requests.py:39-63`), its CLI options, projections and refusal words gain the two fields. A trabajo request without them is refused with a new reason, `trabajo_certificate_figure_missing`, served in the four locales.

### 3. Provider and validator

- `RETENCION_SOPORTADA_NON_CREDIT_ROLES` is replaced by a closed income table keyed by (class, quantity), naming one role each:
  - (`trabajo`, `importe_integro_dinerario`) to `irpf_rendimiento_trabajo_importe_integro_dinerario`;
  - (`trabajo`, `valoracion_especie`) to `irpf_rendimiento_trabajo_especie_valoracion`;
  - (`trabajo`, `ingreso_a_cuenta`) to `irpf_rendimiento_trabajo_especie_ingreso_cuenta`;
  - (`trabajo`, `ingreso_a_cuenta_repercutido`) to `irpf_rendimiento_trabajo_especie_ingreso_cuenta_repercutido`;
  - (`trabajo`, `reducciones_aplicables`) to `irpf_rendimiento_trabajo_reduccion`;
  - (`trabajo`, `gastos_deducibles`) to `irpf_rendimiento_trabajo_gasto_ss_mutualidad`.
  No other class admits an income role.
- The validator refuses, in addition to the accepted refusals:
  - a non-credit quantity whose (class, quantity) pair is absent from the table, or whose target role differs from the pair's role;
  - an income binding reached only as a formula operand, or on a casilla that also carries an alternate binding, a second family binding, or `aeat_prefilled`;
  - once any trabajo income binding is declared, a revision in which a casilla with a role of the table does not take exactly its family binding. This keeps one source per figure.
- `credit_casilla_ids` and the `pago_a_cuenta` branch of `_target_failures` are unchanged.
- The six bindings are declared once, with ids that carry no year (for example `renta-retencion-soportada-trabajo-importe-integro-dinerario`; exact ids are a hypothesis), and casilla overrides set `input_kind = "bound"` on 0003 to 0006, 0011 and 0013. They carry no `aeat_prefilled`, so the borrador never supplies or overrides them. A borrador or datos fiscales cross-check of income is a later decision.

### 4. Parameters and formulas

Each parameter is dated on `filing_period`, cites `ley-35-2006:art-19`, `ley-35-2006:art-20` or `rd-439-2007:art-10` with `required_text` taken from the bundled text, and is resolved by the existing dated selection. Ids are hypotheses; none carries a year.

- `renta-trabajo-otros-gastos-cuantia-general`: 2000, valid from the date the current art. 19.2.f text took effect, 2015-01-01 (catalogue entry `src/cadrumo/_data/registry/aeat/legal/irpf.toml:5968-5988`). Required text "2.000 euros anuales" (`ley-35-2006.html.extracted.md:326`).
- `renta-trabajo-reduccion-art-20`: a `bracket_table` whose rows are the printed tramos. Each row holds its lower and upper bound, the printed amount at the lower bound as `fixed_addition`, and the printed multiplier as a negative `marginal_rate`; a last open row returns 0. Rows are dated by the edition whose manual prints them and cite that manual's table lines (Considerations): the 5.565 table through 2022-12-31, the 6.498 table for 2023, and the 7.302 table from 2024-01-01, open-ended. `BracketEntry` refuses a negative rate today (`src/cadrumo/domain/calculations/registry/schema_formula.py:273-274`). The parameter therefore gains a closed `bracket_kind` with `progressive` (the default and today's rule) and `phase_out` (non-positive rates, each row non-negative at both of its bounds). The field name is a hypothesis.
- `renta-trabajo-reduccion-otras-rentas-limite`: 6500, required text "superiores a 6.500 euros" (`ley-35-2006.html.extracted.md:334`; the same sentence opens every manual table cited above).
- `renta-trabajo-colegio-profesional-limite`: 500 (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:351`).
- `renta-trabajo-defensa-juridica-limite`: 300 (`ley-35-2006.html.extracted.md:325`).

Formulas, in the same fragment, replace the current ones for these casillas through casilla overrides at the baseline:

- 0019 = min(`renta-trabajo-otros-gastos-cuantia-general`, max(0, 0018)). The literal 2000 leaves the registry.
- 0022 = max(0, 0018 - 0019 - 0020 - 0021). This is the art. 19.2.f joint limit accepted as Phase 2a of `2026-07-01-modelo-100-trabajo-casilla-compute-adr`.
- An internal computed node, `rentas-distintas-del-trabajo` (`internal_only`, filed nowhere; precedent `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0001-declarations.toml:1193-1203`), sums by semantic role the net capital mobiliario income of both bases, the net capital inmobiliario income before the art. 23.2 reduction, the net activity income before art. 32 reductions, the imputed income and the computed capital gains and losses, without integration or compensation. The operand roles are enumerated at authoring against the manual definition and each edition's dictionary. An unresolved operand leaves the node, and so 0023, unresolved.
- 0023 = 0 when 0018 is not positive or the node exceeds `renta-trabajo-reduccion-otras-rentas-limite`; otherwise min(lookup_bracket(0018, `renta-trabajo-reduccion-art-20`), max(0, 0022)). The second term keeps the balance non-negative.
- 0025 keeps its formula; with 0023 so bounded it is never negative.
- 0019 and 0023 are listed as inputs in the official design. Their computed flip takes the same design-parity treatment the accepted 0019 flip took.

### 5. Missing, absent and refused

The resolver's states apply per binding as accepted, with one change for income quantities.

- **Recorded**: the sum of the drawn quantity over the class's records.
- **Declared absent**: the profile's categories exclude both `trabajo` and `pension`; every income binding is a proven zero with `PROFILE_FIELD` origin.
- **Missing**: a declared or unknown category with no record and no attestation leaves every income and credit binding unresolved with the existing `RETENCION_SOPORTADA_EVIDENCE_REQUIRED` fact, whose remedy names the record and attest-absence doors. The gate blocks verify, export and local filing.
- **Attested absent**: the attestation keeps its meaning, that income existed and no payer withheld. It zeroes the credit only. Each income binding stays unresolved with a new fact, `RETENCION_SOPORTADA_INCOME_RECORD_REQUIRED`, whose remedy names the record door with origin `operator_declaration` and the attestation's withdrawal, since a record beside an attestation is contradicted. Income is never zero on an attestation.
- **Record from payload v1**: 0003 to 0006 resolve; 0011 and 0013 stay unresolved with the new fact `RETENCION_SOPORTADA_RECORD_FIGURE_MISSING`, whose remedy is to replace the record with the certificate's figures. The credit is unaffected.

No new door is added. The new facts, findings and refusal reasons get served words in the four locales through `dev.locales`.

### 6. Retired advisories

`src/cadrumo/application/modelo/art20_advisory.py` and its call at `src/cadrumo/application/modelo/verification_revision_findings.py:95` are removed with the 0023 flip, together with the mapping fact `src/cadrumo/_data/registry/aeat/facts/2025/mapping/0087-2025-lirpf-art20-reduction-verification-mapping.toml` and its locale key. The ceiling fact `src/cadrumo/_data/registry/aeat/facts/0038-lirpf-art-20-trabajo-reduccion-rnt-ceiling.toml` is removed when no consumer remains.

### 7. Migration

- Stored v1 records stay readable; only their 0011 and 0013 figures need the record replaced. No stored revision is rewritten. A revision persisted under an earlier authority generation replays under its pinned generation; recalculating adopts this decision.
- The personas restate their certificates in the record's terms: `importe_integro` as `importe_integro_dinerario`, `cotizaciones_seguridad_social` as `gastos_deducibles`, and 0.00 where the certificate states none (`dev/fixtures/personas/asalariada-familia/persona.toml:84-91`, `dev/fixtures/personas/arrendador-jubilado/persona.toml:44-52`). Their `not_sourced` entries for 0003 and 0013 become compared values cited to the certificate. They also state 0008, 0009, 0010 and 0024 as zero, since neither derivation names an employer contribution.
- The desktop withholding pane is frozen and is not edited. Its request type and form (`native/desktop/frontend/src/shell/ledgerSetup.ts`, `native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx`) need the two fields when the freeze lifts.

### Verification

- A manual worked example per authored art. 20 table, keyed by semantic role and calculated through the real record store, resolver, registry and gate. The expected values are the printed figures:
  - the 5.565 table: gross 18.300, reducciones 3.060, contributions 610, 3.500 stated on the 0021 role, other income 5.500; neto previo 14.630, reduction 3.292,50, neto reducido 5.837,50 (2022 manual md:8767-8789);
  - the 6.498 table: the same inputs; reduction 5.833,95, neto reducido 3.296,05 (2023 manual md:10699-10721);
  - the 7.302 table: gross 20.300, reducciones 3.060, contributions 3.600, 3.500 stated, other income 5.500; neto previo 13.640, neto 8.140, reduction 7.302, neto reducido 838 (2024 manual md:11121-11140; 2025 manual md:11364-11385).
- For each table, a variant with other income above the limit gives a zero reduction, and a rendimiento neto previo past the last tramo gives zero.
- Every supported year, enumerated from the envelope through `src/cadrumo/domain/calculations/registry/tests/authored_editions.py`: the right table resolves, projected years report `registry_filing_year_projected` with no grade promotion, and existing work-income and 0596 results do not regress.
- The two personas compare 0003, 0013, 0019, 0022, 0023 and 0025 against their cited certificates in every year they declare.
- Refusals: a declared category with no record; an attestation without a record (credit zero, income unresolved); a record beside an attestation; a v1 record; a non-trabajo record carrying the new fields; a trabajo request without them; an unstated 0008 role; 0021 unstated with a stated disability; 0016 above its limit.
- Validator teeth on isolated fixtures: a second source on 0003, `importe_integro` bound to 0003, an income quantity on another class, an income binding as a formula operand, `aeat_prefilled` on an income binding, and a negative rate in a `progressive` table.
- `just check-registry`, `just check-registry-gate`, `just check-bindings`, the report-only edition migration, `just test-registry`, and the year-literal ratchet with no new finding.

### Conditions of acceptance (2026-11-12)

Accepted by the coordinator on 2026-11-12 with these conditions. They bind the implementation.

- **(A) Other-income node.** For the 6.500 test, an income family the profile declares absent is a proven zero; a declared or unknown family without figures leaves the node unresolved. Both are tested: a worker whose profile declares no other income gets the reduction, and one with a declared family lacking figures does not.
- **(B) One statement for the four income boxes.** One action may state 0008, 0009, 0010 and 0024 as zero together, provided its served words name all four boxes; settled in one exchange with the lifecycle owner. A dated profile fact holding "no such contributions" once is a later Step and is not built here.
- **(C) Frozen desktop.** The withholding pane and its payload types get a line in the native-debt register.
- **(D) Delivery units**, about ten commits each, in order: record version 2 and its doors; provider, validator and bindings; parameters and formulas, with the `bracket_kind` registry schema change as its own unit and an authority rebuild; personas with the acceptance owner.

## Rationale

- The record already is the certificate's typed copy, with payer identity, class and evidence. Binding its quantities by role reuses the accepted provider, resolver, applicability rule and gate, and keeps one source per figure. The payer design shows exactly two missing figures, so the record grows by two fields read from the same document.
- Computing 0019, 0022 and 0023 from dated parameters takes the legal amounts out of formula literals and Python constants. Each edition's table becomes data with its citation, and projection applies to it as to any rate.
- Reading art. 20 on the role of 0018 follows the law's own definition and every manual example. The accepted record's 0022 reading would grant the reduction to taxpayers above the threshold.
- The 6.500 gate is computable from casillas the same calculation already resolves. An internal node avoids a second aggregation path and fails closed when any operand is unresolved.
- The blocking and limitation choices apply the 2026-11-11 23:25 principle item by item: income omissions block; deductions are served limitations unless a stored fact shows they apply.

## Consequences

- Gains: the two personas, and every salaried or pensioner profile, get work income from the certificate. The art. 20 reduction and the art. 19.2.f expense are exact in every supported year. The 0022 clamp lands. One advisory and two facts retire.
- Costs: a payload v2 with two required trabajo fields; existing trabajo records must be re-recorded before 0011 and 0013 resolve; four new served facts and findings; a `bracket_kind` field on bracket tables; every return with work income must state 0008, 0009, 0010 and 0024 before it can file; the frozen desktop pane lags the request.
- Reconsider in three cases: a bundled official text shows that the payer certificate states employer contributions (0008, 0009, 0024), which moves them onto the record; the record gains the perceptor key that separates active work from pensions, which lets 0021 be computed from the profile's disability grade and dated parameters; or a DGT or TEAC ruling reads "rentas distintas del trabajo" differently from the manual.

## Proposed wording for the accepted records

Apply only once this proposal is authorized.

`2026-11-01-export-parity-suffered-withholding-schemas-adr`:

- Section 1, quantity bullet: after "`ingreso_a_cuenta_repercutido` or `importe_integro`", add "and, under `2026-11-11-export-parity-work-income-sourcing-adr`, `importe_integro_dinerario`, `valoracion_especie`, `reducciones_aplicables` or `gastos_deducibles`".
- Section 1, last validator bullet: replace "income roles are added only by a later decision." with "the income roles are the (class, quantity) table of `2026-11-11-export-parity-work-income-sourcing-adr`, section 3."
- Section 3, after the `ingreso_a_cuenta_repercutido` field bullet, add: "`reducciones_aplicables` and `gastos_deducibles` (payload v2): required for class `trabajo` and absent for every other class, as fixed in `2026-11-11-export-parity-work-income-sourcing-adr`."
- Section 4: replace "`schema_version` 1" with "`schema_version` 2 (a v1 payload parses with the v2 fields absent)".
- Section 5, "Proven zero": add "An absence attestation proves a zero credit only; it never zeroes an income binding (`2026-11-11-export-parity-work-income-sourcing-adr`, section 5)."

`2026-06-15-art20-trabajo-reduccion-compute-adr`:

- Considerations: replace "rendimiento neto del trabajo (RNT, `0022`)" with "rendimiento neto del trabajo before the art. 19.2.f expenses (RNT, the role of `0018`)".
- Implementation, after the "Shipped (Phase 1, this campaign)" paragraph, add: "Phase 2 is decided by `2026-11-11-export-parity-work-income-sourcing-adr`: `0023` is computed from a dated registry schedule applied to the role of `0018` and gated by a computed other-income node. The Phase 1 advisory, its mapping fact and its ceiling fact are retired."

`2026-07-01-modelo-100-trabajo-casilla-compute-adr`:

- Implementation, Phase 1: replace "The EUR 2.000 and EUR 1.500 figures ride external_constants (e.g. MODELO_100_ART_19_2F_OTROS_GASTOS_EUR, MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR)" with "The EUR 2.000 figure is the dated registry parameter of `2026-11-11-export-parity-work-income-sourcing-adr`; the EUR 1.500 figure rides the registry per revision".
- Implementation, Phase 2a: replace "0019 = min(EUR 2.000, max(0, 0018))" with "0019 = min(the dated art. 19.2.f parameter, max(0, 0018))", and add "Both Phase 2a formulas are delivered by `2026-11-11-export-parity-work-income-sourcing-adr`."
- Considerations, after "MUST stay MANUAL.", add: "An unstated 0021 is a blocking finding when the profile states a taxpayer disability (`2026-11-11-export-parity-work-income-sourcing-adr`)."

## Open questions

None for the operator. The code and bundled texts settle every figure this record computes. Two gaps are recorded as reconsideration conditions rather than questions: the bundled payer design states no employer contributions, and the record does not separate active work from pensions.
