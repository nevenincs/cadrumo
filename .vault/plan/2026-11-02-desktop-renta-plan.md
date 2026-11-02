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
modified: '2026-11-02'
body_schema: body-v2
body_hash: 'sha256:7ba08ef83fbc6ae9def7ad499cef8ff37a9af54a9002a618355ef2a8cda19c84'
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
- [ ] `P01.S02` - [Opus medium] serve descendant, ascendant and patrimonial row groups from the canonical renta_family profile objects (operator ruling 2026-11-02: renta_family.descendiente and ascendiente are canonical; repoint the bindings to them), with a generic generator rule for official repeating elements bounded by the design's repeat limits, row values filled by the profile resolver, and an unfilled group read as unknown rather than empty; `dev/registry/form_layout`.
- [x] `P01.S03` - [Sonnet high] mark the answers the calculation refuses without (1388 earlier negative base, 0168 normal direct estimation) as needing the filer instead of optional; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P01.S04` - [Sonnet high] correct box 0700 so it is not served as an editable optional value left at zero without a formula; `src/cadrumo/_data/registry/aeat/modelos/100`.
- [x] `P01.S05` - [Sonnet high] serve the correction surface on the withholding boxes 0596, 0597 and 0603 so the window can route them to the withholding register; `src/cadrumo/application/modelo/work_form.py`.
- [x] `P01.S06` - [Sonnet high] serve words in every locale for modelo.project version 2 unresolved_bindings and unresolved_casillas and for compare_taxation recommendation reasons; `src/cadrumo/application/modelo/projection_operation.py`.
- [ ] `P01.S07` - [Opus medium] serve Modelo 100 settlement elections in the export offer: refund account, direct debit and the 60/40 split; `src/cadrumo/application/modelo/export.py`.
- [x] `P01.S08` - [Opus medium] register a profile operation that reads and writes the dated imputation criterion per tax year with the wizard's served words; `src/cadrumo/application/wizard/imputation_election.py`.
- [x] `P01.S09` - [Sonnet high] serve declaration_type choices and the descendant and ascendant arrays in user-profile.view; `src/cadrumo/application/user_profile`.
- [x] `P01.S10` - [Opus medium] add a borrador-versus-calculation comparison read over the captured Borrador 100 and the saved calculation; `src/cadrumo/application/live`.
- [x] `P01.S21` - [Sonnet high] degrade a waived refund (0694 above zero) to an unresolved box 0700 with a served reason instead of refusing the whole 2025 calculation; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0001-declarations.toml`.
- [ ] `P01.S22` - [Opus medium] keep the Borrador 100 printed result values as comparison-only observations (never calculation inputs) and author the 2024 and 2025 borrador extraction profiles so the borrador comparison has values to compare; `src/cadrumo/adapters/inbound/borrador`.
- [x] `P01.S23` - [Sonnet high] reconcile the imputation-criterion ADR wording with the implemented rule that an unstated year stays undeclared and is never preselected as devengo; `.vault/adr/2026-11-01-export-parity-income-imputation-criterion-adr.md`.
- [ ] `P01.S24` - [Sonnet high] add a profile writer for renta_family.ascendiente rows mirroring user-profile.descendants, with the four-row cap from the 2025 design and NIF validation, and admit it in the desktop relay; `src/cadrumo/application/user_profile`.

### Phase `P02` - contracts and fixtures

Generated contracts and the fixture generator carry Modelo 100 and the new reads, so the frontend types and stories track the served shapes.

- [x] `P02.S11` - [Sonnet high] regenerate the modelo contract for projection result version 2 and the new reads, and add Modelo 100 to the fixture generator declarations; `native/desktop/frontend/scripts/modelo_fixtures.py`.

### Phase `P03` - relay admission

The desktop relay admits exactly the operations the Renta elements call, each through the closed allow-list.

- [x] `P03.S12` - [Sonnet high] admit user-profile.descendants, live.borrador.100.read and live.borrador.100.query and the new P01 operations in the relay allow-lists; `native/desktop/src-tauri/src/shell`.

### Phase `P04` - Renta workspace elements

The window renders the outline, household, credits, election, comparison, settlement and borrador elements by payload kind over the one generated form.

- [ ] `P04.S13` - [Opus medium] build the Renta workspace shell and outline navigator over the served outline, replacing the prototype grouping; `native/desktop/frontend/src/components/modelo/workspace`.
- [ ] `P04.S14` - [Sonnet high] build the household element from the served profile sections, descendants and minimum boxes; `native/desktop/frontend/src/components/modelo/workspace`.
- [ ] `P04.S15` - [Sonnet high] build the credits element with withholding routing and the projection estimate in served words; `native/desktop/frontend/src/components/modelo/workspace`.
- [ ] `P04.S16` - [Sonnet high] build the imputation election element over the registered profile operation; `native/desktop/frontend/src/components/modelo/workspace`.
- [ ] `P04.S17` - [Sonnet high] build the taxation comparison, settlement and borrador comparison elements by payload kind; `native/desktop/frontend/src/components/modelo/workspace`.
- [x] `P04.S18` - [Sonnet high] retire the Renta prototypes and their prototype-only locale keys now (operator ruling 2026-11-02: Storybook shows only real components over generated fixtures; no prototype copies), so every Renta element is built and reviewed in the real components; `native/desktop/frontend/src/dev/prototypes/renta`.

### Phase `P05` - proof

Stories, Playwright journeys, the no-tax-data guard and locale coverage prove the workspace in en, es, ca and hu.

- [ ] `P05.S19` - [Sonnet high] add Storybook stories over served fixtures for every element state and Playwright journeys for a salaried and an activity filer; `native/desktop/frontend/tests`.
- [ ] `P05.S20` - [Sonnet high] run the no-tax-data guard, desktop chrome and locale parity checks for en, es, ca and hu; `dev/quality/tests/test_window_holds_no_tax_data.py`.

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
