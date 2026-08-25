---
tags:
  - '#plan'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-25'
body_hash: 'sha256:995610b0671c94fff23b96291a16fd31bf188c0b6b6720e9c52a0903ec372697'
tier: L2
related:
  - '[[2026-08-13-registry-suite-red-at-head-audit]]'
  - '[[2026-08-13-m303-compensacion-revision-split-research]]'
  - '[[2026-08-13-registry-suite-red-at-head-adr]]'
---

<!-- RETIRED: S06, S09, S12, S14, S19, S20 -->

# `registry-suite-red-at-head` plan

Action the nine root causes behind the red registry suite, none of which is a
demonstrated wrong number on a return.

## Description

The authorising audit clustered 157 deterministic failures into nine root causes
and found that **none produces a wrong figure on a filing**. That conclusion
survived one reversal: the M303 compensación cluster was first recorded as a
registry defect with over-payment risk and was corrected, on tracing the runtime,
to a defect in the consistency check. The companion research document carries that
correction and the evidence.

Two facts govern how these rows should be read.

**Nothing was hidden.** No test expectation was moved to match the engine anywhere
in this suite. Every failure is a gate that stopped agreeing with the code and was
left red, never a gate re-pointed at the code's current answer. The surviving
assertions still encode what someone believed correct at authoring time.

**The engine is unverified, not vindicated.** Because the M322, M353 and M390
oracles fail at fixture construction, they neither prove the engine right nor
prove it wrong. The honest statement is that the engine is not shown to compute
wrong tax, and is not shown to compute right tax either. Phase `P02` exists to
retire that sentence, and it is retired by the re-runs rather than by the sweeps.

Two rows carry work whose shape is already settled and should not be re-invented.
`P01.S02` has a working model in the tree, named in the row itself. `P02.S10` is
one regression that closes both of the audit's remaining open limits at once and
doubles as the anti-tautology anchor for `P01.S02`.

**This plan carries no authorising ADR, and the schema check flags that as an
error rather than a warning.** The gap is real and is recorded here rather than
silenced. Most rows are repairs with no architectural weight, but two are not:
`P01.S04` changes what an operator-facing verification command asserts, and
`P03.S14` decides how a mid-course AEAT ejercicio split is modelled as registry
revisions. Both are operator rulings. The correct sequence is an ADR covering
those two before either is executed, and this plan should gain it in `related:`
when it exists. The remaining thirteen rows do not depend on that decision and can
proceed against the audit and research documents alone.

## Steps

### Phase `P01` - Repair the gates that are reporting falsely

Three surfaces currently mislead: the relation consistency check fails on its own stale one-revision-per-year assumption, the registry verify verb reports Verificado=True while covering neither relation offsets nor export-layout population, and the deduction-authority guard on the declared-category projection is protected by three constructs that nothing tests. Repair the reporting before acting on anything it reports.

- [x] `P01.S01` - Apply the year delta in the relation consistency check by consuming the anchor helper instead of the period-only wrapper; `src/cadrumo/domain/calculations/registry/tests/test_relation_consistency.py`.
- [x] `P01.S02` - Assert offset-derived source periods against the union of candidate revisions for the resolved source year, copying the existing correct shape at src/cadrumo/application/calculations/_cross_period_clean_state.py lines 167-171 rather than inventing one; `src/cadrumo/domain/calculations/registry/tests/test_relation_consistency.py`.
- [x] `P01.S03` - Add a property guard asserting every declared-category base-only flow value stays outside the deduction-authority refusal trigger set; `src/cadrumo/application/aggregation/tests/`.
- [x] `P01.S04` - Widen the registry verify verb to cover relation offset periods and export-layout population, or make it enumerate the invariant families it does not check; `src/cadrumo/entrypoints/cli/`.

### Phase `P02` - Un-blind the AEAT-grounded oracles

The M322, M353 and M390 manual worked examples fail at fixture construction, before any figure is compared, so they are dark rather than red: they neither prove the engine right nor prove it wrong. Until they execute, the honest position is that these IVA figures are unverified rather than incorrect. In every row in this Phase the sweep is not the deliverable, the re-run is.

- [x] `P02.S05` - Sweep the IvaLedgerObservation fixture builders to declare the deduction authority the real projection carries, deriving it from the invoice classification path rather than choosing a kind that makes the test pass; `src/cadrumo/domain/calculations/registry/tests/`.
- [x] `P02.S11` - Re-run the M322, M353 and M390 manual worked examples and confirm each reproduces its AEAT figure, treating a swept fixture whose oracle has not executed as not done; `src/cadrumo/domain/calculations/registry/tests/`.
- [x] `P02.S07` - Reconcile the surviving IvaLedgerSelector fixture census so every positive constructor supplies cash-accounting treatment and observation-role axes, retain the deliberate missing-role refusal probe, and confirm the focused selector and aggregation suites preserve their exact refusals; `src/cadrumo/domain/calculations/registry/tests/test_binding_reachability_probe.py and src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding.py`.
- [x] `P02.S08` - Supply the renta-2024 maternidad profile binding to the registry-layer M100 harnesses from the production derivation authority, never a hand-picked literal; `src/cadrumo/domain/calculations/registry/tests/`.
- [x] `P02.S10` - Add one regression driving a real 2024 2T negative settlement credit into the 3T return and asserting the resulting compensacion figure; `src/cadrumo/application/calculations/tests/`.
- [x] `P02.S21` - Author modelo 100's ten Anexo A deduction casillas that both bundled dictionaries declare and the registry omits: A/C/E vivienda habitual (LIRPF DT 18), D empresas nueva creacion and M partidos politicos and I bienes de interes cultural (art. 68), F alquiler (DT 15), G/H/J donativos which additionally need a ley-49-2002:art-19 legal entry the catalogue lacks; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas,src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas`.

### Phase `P03` - Close the registry-data defects

A small number of genuine registry gaps sit behind the noise: a revision carrying no export layouts at all, a missing official record position, published AEAT designs attributed to no revision, and a missing locale string. None is a demonstrated wrong number on a current filing, so these rank below the gate repairs.

- [x] `P03.S13` - Diagnose the absent Modelo 390 page-02 field at official record position 1628 before re-anchoring the disclosure-split gate, per that gate's own instruction; `src/cadrumo/_data/registry/aeat/modelos/390/`.
- [x] `P03.S15` - Narrow the Modelo 720 revision 2013-y-siguientes claimed filing years to those its declared layout design covers, or declare the design that covers 2012; `src/cadrumo/_data/registry/aeat/modelos/720/revisions/`.
- [x] `P03.S16` - Set the missing English help string for the standard-rate repercutido casilla through the locales CLI in all four catalogues; `src/cadrumo/locales/`.
- [x] `P03.S17` - Chase the Modelo 180 data_type-vs-diseno mismatch flagged for perc.provincia and perc.modalidad. Verified all 170 casilla-kind fixed-width export fields across the three modelos carrying fixed-width layouts (131, 145, 180) against their bundled diseno at exact offset and length, not a summary table. Confirmed five casilla_ids where AEAT's own Naturaleza column says Numerico and the registry declares data_type text - perc.provincia 76-77, perc.modalidad 78, perc.porcentaje-retencion 93-96, perc.situacion-inmueble 114, perc.inmueble-provincia 321-322, all Modelo 180, both revisions. No further mismatches found beyond these five - Modelo 145 is otherwise fully correct field by field, Modelo 131 has zero casilla-kind text fields at all. Fixed three of five, each by the shape its own diseno text calls for rather than one uniform typing move. perc.modalidad and perc.situacion-inmueble gained value_policy digit-string, refusing non-ASCII-digit content on render and parse without changing the parsed value's type, since each is a single closed-code Numerico slot the export field enum has no dedicated type for. perc.porcentaje-retencion is different in kind, not degree - its diseno text declares 93-96 as one field, Numerico % RETENCION, explicitly subdivided into a 93-94 ENTERO and 95-96 DECIMAL sub-part, a parent field with two Numerico sub-parts rather than an opaque digit string. That shape is a scaled numeric with two decimals, so the fix is data_type decimal with decimals 2 at the export layer, mirrored by data_type ratio at the casilla's own semantic layer to match the established percentage convention elsewhere in the registry, both replacing an earlier digit-string attempt on the same field that only refused non-digit content without correcting the parsed type. Render and parse round-trip verified directly against realistic rates including AEAT's own worked 19 percent example, which renders to wire bytes 1900 exactly. The committed golden fixture's expected value for this casilla was corrected from the string 0000 to Decimal 0.00 to match the corrected parsed type - the fixture's four-digit expectation was the right shape, the declaration's type was wrong, not the other way round. All three fixes verified against the golden parse fixture in both revisions, the full fixed-width codec and schema suites, and a full sequential registry suite run before and after diffed failure-line by failure-line, showing a clean one-test net improvement (167 to 166 failed) with zero collateral regressions across three separate full runs. Declined the other two, each for a concrete reason rather than force-fitting a fix. perc.provincia and perc.inmueble-provincia are left_zero right-justified two-character province-code fields - the registry's own build-time validator requires digit-string to pair with padding none, and requires allowed_values to pair with value_policy enumerated-digits which itself requires data_type integer, and integer changes the parsed value from str to Decimal and breaks the existing golden fixture that asserts a string - no safe fix exists at this field shape without a design decision this row does not make. Confirmed via the diseno's own wording, los dos digitos numericos, that both province fields are always exactly two digits with no legitimate blank case, which narrows what a future padding change could break to that single verified case. Two further candidates, perc.inmueble-codigo-municipio and perc.inmueble-codigo-postal, are plausibly numeric INE and postal codes but the diseno's own text does not use the word numerico for either, unlike provincia which does - left unconfirmed rather than assumed. Did not touch the fixed-width codec, which unblock-export owns live and uncommitted.; `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0002-modelo-180-perceptor.toml, src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0002-modelo-180-perceptor.toml, src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/casillas/cperc.porcentaje-retencion.toml, src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/casillas/cperc.porcentaje-retencion.toml`.
- [x] `P03.S18` - Sweep every export field declaring padding left_zero across all modelos and both directory shapes, export_layouts and export, since Modelo 349 uses the latter. 127 total fields, 12 files across Modelo 131, 145, 180 and 349. Classification is structural, not per-field judgement - integer, decimal and money fields are always safe because Decimal of int of digits is indifferent to leading zeros, so the parse-side lstrip is inert once the value is reinterpreted numerically - 108 of 127. Only data_type text fields return the stripped string directly with no numeric reinterpretation, and 19 of those are genuine fixed-width identifiers whose value space includes leading zeros by construction rather than zero-fillable quantities - NIF, dos digitos numericos provincia codes 01-52, INE municipio codes and Spanish codigo postal codes, all province-prefixed. Confirmed the class is live, not latent - src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py parses a Sede-captured filed declaration's fixed-width bytes back into persisted ObservedCasillaValue and ObservedHeaderFact records for every casilla-kind and header-kind field, taking the post-unpad string unchanged with no downstream re-validation, so a previously-filed Modelo 180 or 349 declaration carrying a low-numbered NIF or a province, postal or municipio code in 01-09 gets silently shortened on capture and that wrong value then carries forward into previous-filing bindings for later years. Fixed the 19 by changing padding from left_zero right to none none, which is what these fields structurally are - fixed-width identifiers that always exactly fill their slot, never actually padded by left_zero on render, only ever damaged by its unpad on parse. Did not touch the codec, only the nineteen field declarations, across two Modelo 180 revisions times eight ids and one Modelo 349 revision times three ids. Proved byte-for-byte render identity for every present value across all nineteen fields by direct rendering under both declarations and diffing, zero mismatches across fifty seven sampled values including low-numbered NIFs and provinces 01, 09, 28 and 52. The absent-value behaviour does move, and this is the one place render output changes - today an absent required-in-practice text field renders as a string of zeros, for example 000000000 for a NIF or 00 for a province, which looks like plausible data rather than an omission - after the fix it renders as spaces, an honest blank. Neither is correct for a field that is actually required, and both are covered by the pending fix making required bite for text, but the row states the behaviour moved rather than letting a reader discover it. Wrote a regression test exercising the real capture path, not the codec in isolation - test_low_numbered_identifiers_survive_submitted_file_capture in the sede adapter's declarations test module builds a synthetic Modelo 180 filed declaration carrying a low-numbered NIF and a province of 01 for six of the nineteen fields including one header field, feeds it through _observed_casillas_from_submitted_file and _observed_header_facts_from_submitted_file exactly as the production capture path calls them, and asserts every persisted value retains its leading zeros. Proved the test would have failed before the fix via a runtime monkeypatch of the loaded field objects back to left_zero right, outside the repo and without touching the tracked registry file, reproducing the exact corruption - 00098765Z became 98765Z, 01 became 1, 01001 became 1001 - confirming the test is the one that would have caught this.; `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0001-modelo-180-declarante.toml, src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0002-modelo-180-perceptor.toml, src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0001-modelo-180-declarante.toml, src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0002-modelo-180-perceptor.toml, src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0010-record-declarante.toml, src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0020-record-operador.toml, src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0030-record-rectificacion.toml, src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py`.
- [ ] `P03.S22` - Rebaseline the live claimed-year layout-design gate against HEAD by routing Modelos 126, 128, 165, 181, 184, 270, 308, 309, 341, 353, and 576 historical design underhangs to temporal coverage and official-design acquisition authority, reusing existing export authority for Modelo 200, adjudicating Modelo 180 presentation-year and Modelo 210 end-window semantics before registry edits, and keeping this campaign open until the whole-tree gate passes; `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md, .vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md, .vault/plan/2026-08-24-deadline-window-revision-authority-plan.md, src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`.
- [ ] `P03.S23` - Drain the 2026-08-25 isolated registry rebaseline by reconciling the reproducible failures into single-home clusters for temporal and design authority, filing-grade and export capability, continuity enrollment, stale synthetic fixtures and scenario declarations, parser coverage, public-boundary imports, validator reviewability, and verdict-cache behavior, removing stale expectations where current authority disproves them and retaining real gaps under their owning plans until every isolated node and the sequential whole-tree suite pass; `src/cadrumo/domain/calculations/registry/tests, .vault/plan/2026-08-14-registry-temporal-coverage-plan.md, .vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md, .vault/plan/2026-08-24-registry-completeness-closure-plan.md, .vault/plan/2026-08-24-deadline-window-revision-authority-plan.md`.

## Parallelization

`P01` should land before `P02` and `P03`. Its rows repair surfaces that currently
report falsely, and acting on a false report is how the audit's own first verdict
went wrong. Within `P01`, `S01` and `S02` touch one file and are one commit, not
two. `S03` and `S04` are independent of everything.

`P02.S05` blocks `P02.S11`, and that ordering is the point of the Phase: the sweep
without the re-run leaves the oracles exactly as dark as they are now. The other
`P02` rows are mutually independent. `P03` rows are independent of each other and
of everything else.

**Blocked on the repository lock.** Every row is currently unstartable for commit
purposes: `.git/index.lock` is orphaned and blocks all commits. That is with the
operator. Work may be authored, but no row closes until commits are possible.

**Operator-gated rows, needing a ruling rather than an implementation choice.**
`P01.S04` changes what an operator-facing verification command asserts, so the
decision of whether to widen its coverage or to make it disclose its scope belongs
to the operator, not the implementer. `P03.S12` and `P03.S15` each offer author-it
or retire-the-claim, and choosing wrongly either fabricates AEAT structure or
silently narrows declared coverage. `P03.S14` authors registry data attributing
published AEAT designs and needs the tax-review provenance the grounding rules
require. `P02.S09` is owned elsewhere and must be coordinated with the
canonical-identifiers campaign rather than swept unilaterally.

**Peer contention.** Several agents were mid-flight in
`src/cadrumo/domain/calculations/registry/tests/` and
`src/cadrumo/application/` when this plan was authored. Diff against `HEAD` before
the first edit on any row.

## Verification

`P01` is verified when the relation consistency gate passes for the right reason.
That is a stronger bar than green: after `S01` and `S02`, deliberately break a real
relation fragment and confirm the gate reds, then restore. A gate that stopped
firing because its assertion was weakened is the failure mode being repaired, and
it would look identical to success. `S03` is verified by the same discipline -
temporarily add a trigger-set value to the closed flow table from outside the
repository and confirm the guard fails.

`P02` is verified only by executing oracles. A swept fixture is not evidence. The
Phase closes when the M322, M353 and M390 worked examples run and each reproduces
its AEAT manual figure, and when no expected value in any swept fixture was
authored by reading the engine's current output. Until then the standing statement
holds: the engine is not shown to compute wrong tax and is not shown to compute
right tax either.

`P02.S10` is the single regression that closes both limits the authorising audit
declared open - whether the revision-stamp re-confirmation selects the correct half
for a 2T source, and whether the carry produces the right number end to end. Build
it once and cite it for both. It also exercises the exact crossing `P01.S02`
repairs, so it doubles as that row's anti-tautology anchor.

`P03` is verified per row against the official AEAT source that establishes the
structure, never against the engine's own output.

The plan is complete when every row is closed and the full unit lane is green in a
completed CI run - not a queued one. At authoring time the workflow had not
completed a run since 2026-08-07, which is why three unswept schema changes reached
main in the first place.
