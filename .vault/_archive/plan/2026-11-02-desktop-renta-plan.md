---
tags:
  - '#plan'
  - '#desktop-renta'
date: '2026-11-02'
tier: L2
related:
  - '[[2026-11-02-desktop-renta-adr]]'
  - '[[2026-09-07-tuimodelo-form-projection-adr]]'
  - '[[2026-09-30-modelo-editor-workbench-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-23-desktop-modelo-workspace-adr]]'
  - '[[2026-11-02-operation-refusal-words-adr]]'
  - '[[2026-11-01-export-parity-income-imputation-criterion-adr]]'
  - '[[2026-06-02-modelo-multiyear-renta-adr]]'
  - '[[2026-11-02-desktop-renta-renta-family-canonical-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-adr]]'
  - '[[2026-11-03-backend-served-surface-plan]]'
modified: '2026-11-03'
body_schema: body-v2
body_hash: 'sha256:15b88897aa6c78bc78cc5f43b6454ec263a3110c8a4e7b74d1c6fd64ebf45365'
---

# `desktop-renta` plan

The desktop Renta (Modelo 100) workspace: one generated form plus served companion reads.

## Description

Approved 2026-11-02. The operator approved this plan and accepted `2026-11-02-desktop-renta-adr` in the tui frontend session ("renta and adr are approved, execute"); the approval covers every Phase, including the P01 backend read-model Steps.

Implementation decisions, made by the implementing session on 2026-11-02 because the operator delegated the specifics: an unstated imputation criterion stays undeclared and is never preselected as devengo, because the window may not infer a taxpayer election and the calculation already keeps the year unresolved (P01.S23 aligns the ADR); a waived refund leaves only box 0700 unresolved instead of failing the whole return, because unresolved inputs degrade locally (P01.S21); earlier-period carries within the campaign (130 box 05, 131 box 11, the 303 compensation carry) stay waiting rather than needs-you, because the product produces them from its own earlier declarations; and Borrador printed results are kept as comparison-only observations, never calculation inputs, so the comparison can confirm or contradict the local result (P01.S22).

Build the desktop Renta (Modelo 100) workspace as one generated form with backend-served companion reads that the window renders by payload kind.

Decision coverage: `2026-11-02-desktop-renta-adr` (accepted) settles the boundary between the generated form and the companion reads, and it governs every Phase. `2026-09-07-tuimodelo-form-projection-adr`, `2026-09-30-modelo-editor-workbench-adr` and `2026-10-23-desktop-modelo-workspace-adr` govern P01.S01 to P01.S05 and P04. `2026-11-02-operation-refusal-words-adr` governs P01.S06 and every served word. `2026-11-01-export-parity-income-imputation-criterion-adr` governs P01.S08 and P04.S16. `2026-06-02-modelo-multiyear-renta-adr` governs the earlier-year answer in P01.S03. `2026-10-05-desktop-design-system-adr` governs P04 and P05. The ADR is accepted.

Gap analysis, per section of the 2025 revision:

- Generated and kept as served: the box editors, origins and editability of every section (employment, movable capital, real estate, activities, capital gains, bases, liability, payments on account, result). The form view draws them unchanged.
- Generated, but backend gaps block use: navigation, because 75 of 87 section headings are technical tokens and section counts show no needs-you or blocked boxes; descendants and ascendants, which are flat boxes without row groups; the answers 1388 and 0168, which the calculation requires but the form serves as optional; and box 0700, which is served as editable and left at zero with no formula (P01.S01 to P01.S04).
- Bespoke companion reads: the household (`user-profile.view` lacks declaration_type choices and the descendant arrays, and `user-profile.descendants` is not admitted; P01.S09, P03.S12); the imputation election (no registered operation, written only by the setup flow; P01.S08); the taxation comparison (`modelo.work.compare_taxation` reasons are English-only free text; P01.S06); settlement (the Modelo 100 export offer serves no elections; P01.S07); the borrador comparison (no comparison read exists; P01.S10); and the projection estimate (`modelo.project` result version 2 on feature/renta-withholding serves tokens and no words; P01.S06, P02.S11).
- Credits: boxes 0596, 0597 and 0603 come from the withholding register. `modelo.project` refuses a caller value for them, so no element offers manual entry. The form must serve their correction surface (P01.S05). Unresolved credits and the totals 0609 and 0610 that read them stay unresolved, never zero.
- Not usable: `modelo.work.wizard_context` serves Spanish labels and raw binding ids in every language and omits 1388. It is not a source for any element.

The design prototypes are the Storybook stories under `Prototypes/Renta/` in `native/desktop/frontend/src/dev/prototypes/renta/`. They use fixtures read through the application's own read path for a synthetic taxpayer, and they mark every missing read as not served.

## Steps

### Phase `P01` - backend read-model gaps for Modelo 100

The application serves every word, grouping and state the Renta workspace draws, so the window computes nothing.

- [x] `P01.S01` - [Opus medium] serve a Renta outline from the registry: reviewed localized headings for the 75 technical sections, outline groups, page and section applicability, and section attention counts that roll up needs-you and could-not-calculate boxes; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P01.S02` - [Opus medium] serve descendant, ascendant and patrimonial row groups from the canonical renta_family profile objects (operator ruling 2026-11-02: renta_family.descendiente and ascendiente are canonical; repoint the bindings to them), with a generic generator rule for official repeating elements bounded by the design's repeat limits, row values filled by the profile resolver, and an unfilled group read as unknown rather than empty; `dev/registry/form_layout`.
- [x] `P01.S03` - [Sonnet high] mark the answers the calculation refuses without (1388 earlier negative base, 0168 normal direct estimation) as needing the filer instead of optional; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P01.S04` - [Sonnet high] correct box 0700 so it is not served as an editable optional value left at zero without a formula; `src/cadrumo/_data/registry/aeat/modelos/100`.
- [x] `P01.S05` - [Sonnet high] serve the correction surface on the withholding boxes 0596, 0597 and 0603 so the window can route them to the withholding register; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P01.S06` - [Sonnet high] serve words in every locale for modelo.project version 2 unresolved_bindings and unresolved_casillas and for compare_taxation recommendation reasons; `src/cadrumo/application/modelo/projection_operation.py`.
- [x] `P01.S07` - [Opus medium] serve Modelo 100 settlement elections in the export offer: refund account, direct debit and the 60/40 split; `src/cadrumo/application/modelo/export.py`.
- [x] `P01.S08` - [Opus medium] register a profile operation that reads and writes the dated imputation criterion per tax year with the wizard's served words; `src/cadrumo/application/wizard/imputation_election.py`.
- [x] `P01.S09` - [Sonnet high] serve declaration_type choices and the descendant and ascendant arrays in user-profile.view; `src/cadrumo/application/user_profile`.
- [x] `P01.S10` - [Opus medium] add a borrador-versus-calculation comparison read over the captured Borrador 100 and the saved calculation; `src/cadrumo/application/live`.
- [x] `P01.S21` - [Sonnet high] degrade a waived refund (0694 above zero) to an unresolved box 0700 with a served reason instead of refusing the whole 2025 calculation; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0001-declarations.toml`.
- [x] `P01.S22` - [Opus medium] keep the Borrador 100 printed result values as comparison-only observations (never calculation inputs) and author the 2024 and 2025 borrador extraction profiles so the borrador comparison has values to compare; `src/cadrumo/adapters/inbound/borrador`.
- [x] `P01.S23` - [Sonnet high] reconcile the imputation-criterion ADR wording with the implemented rule that an unstated year stays undeclared and is never preselected as devengo; `.vault/adr/2026-11-01-export-parity-income-imputation-criterion-adr.md`.
- [x] `P01.S24` - [Sonnet high] add a profile writer for renta_family.ascendiente rows mirroring user-profile.descendants, with the four-row cap from the 2025 design and NIF validation, and admit it in the desktop relay; `src/cadrumo/application/user_profile`.
- [x] `P01.S25` - [Sonnet high] ground the instalment-split fact back to every supported filing year so 2022-2024 returns keep the split, refuse the split when the second instalment would be zero, and refuse settlement for years without a computed 0700 while 0693 is above zero; `src/cadrumo/_data/registry/aeat/facts/0175-payment-instalment-split.toml`.
- [x] `P01.S27` - [Sonnet high] make modelo.project default the region from the profile's tax residence, serve a per-revision projectable capability, serve words for the m100 projection and m130 accumulated figures, and replace the CLI command in its refusal words with a served desktop action; `src/cadrumo/application/modelo`.
- [x] `P01.S28` - [Sonnet high] keep the form's attention counts equal to what its outline reaches by serving a kept-apart outline group for working figures and one for unplaced boxes whenever each is non-empty, so a failed working figure or an unplaced box that needs the filer stays counted and reachable; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P01.S29` - [Sonnet high] make modelo.project refuse a target whose revision the registry projection mapping does not name, using the same check that serves projectable; `src/cadrumo/application/modelo/projection_operation.py`.
- [x] `P01.S30` - [Sonnet high] make the user-profile.descendants writer validate a descendant NIF's control letter with the same canonical validator the ascendants writer uses, refusing with a row-numbered served reason; `src/cadrumo/application/user_profile/descendant_rows.py`.
- [x] `P01.S32` - [Opus medium] make modelo.work.compare_taxation run on the work unit's own held values (entered, imported, ledger and prior-period evidence) and refuse only when a box the comparison actually reads is unresolved, naming those boxes in served words; serve compares_taxation and compares_borrador on the work form from the revision's declarations so the window offers each comparison only where it applies; `src/cadrumo/application/modelo/taxation_comparison.py`.
- [x] `P01.S33` - [Opus medium] make the Art. 50.3 compensation gates refuse a positive 1389 when the pending stock 1388 or the computed ceiling is zero or missing, and refuse a 1389 below the ceiling because art. 50.3 LIRPF requires compensation in the maximum amount each year allows; `src/cadrumo/application/modelo/verification_predicates.py`.
- [x] `P01.S34` - [Sonnet high] apply the P01 re-review's low findings: settlement_unsupported words that say Cadrumo does not compute the remainder, the family rows docstring, a neutral synthetic fixture source key, a household row limit resolved from the registry instead of a modelo constant, and refused-NIF exceptions raised from None; `src/cadrumo/application/user_profile/household_row_limit.py`.
- [x] `P01.S35` - [Opus medium] model the art. 50.3 compensation chain for every origin year: 0501 sums every applied row (1381, 1383, 1386, 1389 and their siblings) with each row capped by the maximum left after older rows are applied first, and give every supported edition before 2025 the same stock and maximum gates instead of a free manual 0501; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/verification_predicates/0001-declarations.toml`.
- [x] `P01.S36` - [Sonnet high] make the estimate serve a typed next step when a calculated quarter cannot yet produce box 19 because its earlier-filing answers are missing, naming the quarter's open inputs, so the estimate never ends on the generic projection failure; `src/cadrumo/application/modelo/projection_next_steps.py`.
- [x] `P01.S38` - [Sonnet high] declare the filing-mode role on Modelo 100 revisions 2022 to 2024 where their official designs carry the individual or joint declaration type, so the taxation comparison is served for those years; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`.
- [x] `P01.S39` - [Opus medium] serve every writable binding override a revision's edit surface admits as an answerable field on the work form, placed by the layout or in a served answers group, so a declaration never asks for an answer the window cannot take (such as Modelo 130's previous-year activity income and earlier negative results); `src/cadrumo/application/modelo/work_form.py`.
- [x] `P01.S40` - [Sonnet high] declare in the registry which declaration owns each household row object's repeat limit, so the profile writer reads the limit directly instead of scanning every modelo's annual revision; `src/cadrumo/application/user_profile/household_row_limit.py`.
- [x] `P01.S41` - [Opus medium] place box 0500 before the art. 50.3 compensation as the AEAT design does, compute 1391 from the chain instead of a manual input, and find whether 448b84d73d broke test_work_calculate_modelo_100_routes_autonoma_auto_ledger_expenses on box 0171, fixing the cause if so; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/formulas/0001-declarations.toml`.
- [x] `P01.S42` - [Sonnet high] make modelo edit admission refuse an override the work form serves no field or answer for (such as Modelo 720 baselines and the 131 and 720 row-field bindings), so the writable surface and the served form agree; `src/cadrumo/application/modelo/edit_admission.py`.
- [x] `P01.S43` - [Sonnet high] resolve the renta-ledger and counterpart declarations through the registry's canonical temporal selection so a filing year without an authored edition projects to the nearest one instead of raising 'no registry revision in force'; `src/cadrumo/application/aggregation/renta_ledger.py`.
- [x] `P01.S44` - [Sonnet high] establish what verification and export do with a Modelo 100 year above the newest authored edition, keep a projected year from carrying filing grade as the registry temporal coverage decision requires, and link that decision in the plan; `src/cadrumo/application/modelo/verification_actions.py`.
- [ ] `P01.S45` - [Sonnet high] derive the years every Renta test exercises from the support declaration and the authored editions, take the fixture generator year from the registry, and read projection from a served field instead of the revision id; `src/cadrumo/application/modelo/tests/test_modelo_100_art_50_3_compensation_verification.py`.
- [x] `P01.S46` - [Opus medium] serve, per withholding credit, the calculated boxes that depend on it so the credits panel stops walking formula operands in the window; `native/desktop/frontend/src/components/modelo/workspace/creditBoxes.ts`.
- [x] `P01.S47` - [Opus medium] ground box 0506 in LIRPF art. 84.2.3 and the AEAT design, applying the remainder of the joint reduction to the savings base, so the joint calculation and comparison do not over-tax savings income; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/formulas/0001-declarations.toml`.
- [x] `P01.S48` - [Sonnet high] resolve the low plan-close findings: required authored_year, settlement-unsupported words naming a waived refund in all four locales; `src/cadrumo/application/modelo/profile_derived_facts.py`.
- [x] `P01.S49` - [Sonnet high] mirror the merged backend on the desktop: regenerate the modelo and ledger contracts for the disagreement operations and the form note finding id, and give the withholding certificate record a certificate file picker with served words for the custody refusals; `native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx`.
- [x] `P01.S50` - [Sonnet high] let a projected Modelo 100 year resolve the Anexo D inventory applicability through the registry selection instead of an exact year match, and serve state-projection readiness at the grade the year reaches; `src/cadrumo/application/aggregation/inventory.py`.
- [x] `P01.S51` - [Opus medium] design and [Sonnet high] build the Modelo workspace door for a blocking credit or tier disagreement: list the served disagreements, accept one with a reason and revoke an acceptance at its expected revision, all in served words with stories and a scenario; `native/desktop/frontend/src/components/modelo/workspace`.
- [x] `P01.S52` - [Sonnet high] show the withholding record's served refusal words for the three certificate custody refusals in the withholding pane, as invoice add already shows its served words; `native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx`.
- [x] `P01.S53` - [Sonnet high] once the withholding record serves refusal words for every reason, delete the pane's own desktop.ledger.withholding.refusal words so the window holds no words of its own for the operation; `native/desktop/frontend/src/components/ledger/setup/setupWords.ts`.
- [x] `P01.S54` - [Sonnet high] delete the ledger classification constants and their classify rules now that the backend serves the classification flags; the rest of the window deletions run under the backend-served surface plan; `native/desktop/frontend/src/shell/ledgerContract.ts`.

### Phase `P02` - contracts and fixtures

Generated contracts and the fixture generator carry Modelo 100 and the new reads, so the frontend types and stories track the served shapes.

- [x] `P02.S11` - [Sonnet high] regenerate the modelo contract for projection result version 2 and the new reads, and add Modelo 100 to the fixture generator declarations; `native/desktop/frontend/scripts/modelo_fixtures.py`.

### Phase `P03` - relay admission

The desktop relay admits exactly the operations the Renta elements call, each through the closed allow-list.

- [x] `P03.S12` - [Sonnet high] admit user-profile.descendants, live.borrador.100.read and live.borrador.100.query and the new P01 operations in the relay allow-lists; `native/desktop/src-tauri/src/shell`.

### Phase `P04` - Renta workspace elements

The window renders the outline, household, credits, election, comparison, settlement and borrador elements by payload kind over the one generated form.

- [x] `P04.S13` - [Opus medium] build the Renta workspace shell and outline navigator over the served outline, replacing the prototype grouping; `native/desktop/frontend/src/components/modelo/workspace`.
- [x] `P04.S14` - [Sonnet high] build the household element from the served profile sections, descendants and minimum boxes; `native/desktop/frontend/src/components/modelo/workspace`.
- [x] `P04.S15` - [Sonnet high] build the credits element with withholding routing and the projection estimate in served words; `native/desktop/frontend/src/components/modelo/workspace`.
- [x] `P04.S16` - [Sonnet high] build the imputation election element over the registered profile operation; `native/desktop/frontend/src/components/modelo/workspace`.
- [x] `P04.S17` - [Sonnet high] build the taxation comparison, settlement and borrador comparison elements by payload kind; `native/desktop/frontend/src/components/modelo/workspace`.
- [x] `P04.S18` - [Sonnet high] retire the Renta prototypes and their prototype-only locale keys now (operator ruling 2026-11-02: Storybook shows only real components over generated fixtures; no prototype copies), so every Renta element is built and reviewed in the real components; `native/desktop/frontend/src/dev/prototypes/renta`.
- [x] `P04.S26` - [Sonnet high] forward the served refusal reason and words through the desktop host's profile write path instead of the bare code, and serve a per-revision flag naming which declarations ask the imputation election so the window stops gating on the profile source group; `native/desktop/src-tauri/src/shell/user_profile.rs`.
- [x] `P04.S31` - [Sonnet high] serve the estimate refusal's remedy as a typed next step in the same shape the work form serves next_action (kind, target declaration address, served words) and let the window offer it through the existing next-action handling, so the window holds no table of operator action ids; `src/cadrumo/application/modelo/projection_operation.py`.
- [x] `P04.S37` - [Sonnet high] ask whether a single parent lives with the child's other parent in the profile wizard's family section and the desktop household element, writing renta_family.convive_con_otro_progenitor through the canonical profile writer; `src/cadrumo/application/wizard/setup_family_sections.py`.

### Phase `P05` - proof

Stories, Playwright journeys, the no-tax-data guard and locale coverage prove the workspace in en, es, ca and hu.

- [x] `P05.S19` - [Sonnet high] add Storybook stories over served fixtures for every element state and Playwright journeys for a salaried and an activity filer; `native/desktop/frontend/tests`.
- [x] `P05.S20` - [Sonnet high] run the no-tax-data guard, desktop chrome and locale parity checks for en, es, ca and hu; `dev/quality/tests/test_window_holds_no_tax_data.py`.

## Parallelization

P01 Steps are independent of each other and can run in parallel, except that P01.S03 and P01.S05 touch the same form builder as P01.S01 and land after it. P02.S11 follows the P01 Steps whose shapes it regenerates. P03.S12 can run beside P01 for the existing operations and is completed after P01.S08 and P01.S10 register theirs. P04.S13 follows P01.S01 and P02.S11. P04.S14 to P04.S17 can run in parallel once P04.S13 lands, each after its own P01 read. P04.S18 runs last in P04. P05 follows P04. Each parallel worker owns disjoint files. Contract regeneration and locale catalogue writes are serialized.

## Verification

- Every P01 read is covered by tests through the real owning read path, for success, refusal and the unresolved, unknown, advisory and proven-zero states, in en, es, ca and hu.
- Storybook builds with `CADRUMO_CMAKE_BINARY_DIR` set, and every element has stories for its served states over fixtures generated by `native/desktop/frontend/scripts/modelo_fixtures.py`.
- Playwright journeys for a salaried filer and an activity filer reach a result, route the withholding boxes to the register, and never offer manual entry for 0596, 0597 or 0603.
- `dev/quality/tests/test_window_holds_no_tax_data.py` passes, and the window holds no mapping of tax tokens to words.
- The desktop chrome and locale parity tests pass. New keys go through `python -m dev.locales set-batch` with real translations, addressing the user informally in the singular.
- `npx tsc --noEmit -p .`, eslint and prettier pass in `native/desktop/frontend`.
- Phase-close and plan-close reviews pass.
