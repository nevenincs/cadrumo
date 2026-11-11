---
tags:
  - '#plan'
  - '#persona-table'
date: '2026-11-11'
tier: L2
related:
  - '[[2026-11-05-per-activity-estimation-regime-adr]]'
  - '[[2026-11-03-backend-served-surface-adr]]'
  - '[[2026-10-18-runtime-authority-boundary-adr]]'
modified: '2026-11-11'
body_schema: body-v2
body_hash: 'sha256:80e3b9bfd4a457888f005b5434555c7b2fd68d7fe9a0ac02d5afb50e275a9557'
---

# `persona-table` plan

Make the Python backend calculate, verify and export every return the nine fixture personas must file, then take up the deferred backend scope and the frozen desktop work.

## Description

Approved 2026-11-11. Authorization basis: the operator's directive of 2026-11-11 giving the coordinating session authority to plan and organise all development, and the operator's instruction of the same day to close every plan then in flight and track only the real remaining work in one new plan.

Decision coverage: this plan makes no costly decision. It sequences work inside decisions already accepted. Three Steps in `P02` rest on an accepted decision and are bounded by it: `P02.S21` by `2026-11-05-per-activity-estimation-regime-adr`, `P02.S22` by `2026-11-03-backend-served-surface-adr`, and `P02.S24` by `2026-10-18-runtime-authority-boundary-adr`. The Steps of `P01` enforce official AEAT rules and existing decisions; a Step that turns out to need a new or changed decision stops and raises it before any code.

What this plan replaces. On 2026-11-11 the vault held 76 plans in flight with 506 open Steps between them, most untouched since early November while the work was being driven from a defect register. All 76 were archived unchanged under `.vault/_archive/plan/`, together with the 70 execution ledgers that belonged only to them. Their open Steps were classified and the backend ones checked against the tree. What remained real is carried here. The rest was discarded: Steps already done in the code, Steps the persona table now proves, review and close-out Steps, tooling and refactoring campaigns, and export layouts for modelos no persona files.

Definition of done for `P01`. The persona table has one row per persona, modelo, year and period. A row is green when a live calculation equals an expectation that cites its official source, verification is granted, and export writes a file valid against the official design. A row replayed from persona history, or one whose expectation has no source, is not green. The table at tui `3898285ace` had 132 rows for four modelos and no live-calculated row passing export; a few shared causes blocked almost every row, and each Step of `P01` is one such cause, named with the lane that owns it.

`P02` holds backend work verified as not done on 2026-11-11: only the 2024 edition of Modelo 200 has formulas and Modelo 840 has none; no test covers a correction of a correction; the profile schema has only the taxpayer-wide estimation regime; no datos fiscales parser exists; the login, session, access and custody modules still live in the tax package; and the window still carries 25 word-map files that backend operations do not yet replace.

`P03` is frozen. When the freeze began, 39 native commits on feature/tui had never been built, among them the on-demand local AI server.

## Steps

### Phase `P01` - Persona table green

Every persona row passes calculate, verify and export, proven in Python with no native build. A Step is checked only when the persona table shows the rows it names green on a feature/tui head.

- [ ] `P01.S01` - Promote the persona table runner into the repository, with a committed per-row baseline and a summary that counts live passes apart from history-filed, unverified and unsupported rows (lane ACCEPTANCE); `dev/acceptance/persona_table`.
- [ ] `P01.S02` - Add table rows for every modelo each of the nine personas is obliged to file, for every supported year taken from the registry envelope (lane ACCEPTANCE, cause C1); `dev/acceptance/persona_table, dev/fixtures/personas`.
- [ ] `P01.S03` - Chain periods in the table so each quarter is filed locally before the next is calculated, through to the annual modelo (lanes ACCEPTANCE and LIFECYCLE, cause P3); `dev/acceptance/persona_table, src/cadrumo/application/modelo`.
- [ ] `P01.S04` - Clear the cross-period dependency that blocks first-quarter Modelo 130 verification for every persona and year (lanes LIFECYCLE and CALC-PAGOS, cause P1); `src/cadrumo/application/modelo/verification_cross_period.py, dev/fixtures/personas`.
- [ ] `P01.S05` - Ground the Modelo 130 gastos de dificil justificacion percentage for each year in the official text and make expectation and calculation agree (lane CALC-PAGOS, cause P2); `src/cadrumo/_data/registry/aeat/modelos/130, dev/fixtures/personas`.
- [ ] `P01.S06` - Make every Modelo 111, 115, 180 and 190 row pass calculate, verify and export (lane CALC-PAGOS); `src/cadrumo/_data/registry/aeat/modelos/111, src/cadrumo/_data/registry/aeat/modelos/115, src/cadrumo/_data/registry/aeat/modelos/180, src/cadrumo/_data/registry/aeat/modelos/190, src/cadrumo/application/aggregation`.
- [ ] `P01.S07` - Make Modelo 100 calculate for 2024 for every persona by correcting formula 0613 (lane CALC-RENTA, cause R1); `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas`.
- [ ] `P01.S08` - Resolve Modelo 100 box 0604 and the boxes derived from it once Modelo 130 quarters are filed (lane CALC-RENTA, cause R2); `src/cadrumo/application/aggregation, src/cadrumo/_data/registry/aeat/modelos/100`.
- [ ] `P01.S09` - Resolve the Modelo 100 inventory bindings behind boxes 0177, 0181 and 0182 (lane CALC-RENTA, cause R3); `src/cadrumo/domain/contribuyente/inventory, src/cadrumo/_data/registry/aeat/modelos/100`.
- [ ] `P01.S10` - Supply the Modelo 100 XML content the official schema requires, starting with descendant and ascendant names (lane CALC-RENTA, cause R4); `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/application/filing`.
- [ ] `P01.S11` - Settle from the official rule whether a Modelo 100 refund needs a stated account, and make the persona data or the refusal conform (lane CALC-RENTA, cause R5); `src/cadrumo/application/modelo, dev/fixtures/personas`.
- [ ] `P01.S12` - Assert Modelo 303 values on live calculations and make the export of every 303 quarter succeed, filed quarters included (lane CALC-IVA, cause I1); `src/cadrumo/_data/registry/aeat/modelos/303, src/cadrumo/application/filing/producer_snapshot.py`.
- [ ] `P01.S13` - Make every Modelo 390, 349 and 347 row pass, with a typed refusal when no Modelo 347 is due (lane CALC-IVA); `src/cadrumo/_data/registry/aeat/modelos/390, src/cadrumo/_data/registry/aeat/modelos/349, src/cadrumo/_data/registry/aeat/modelos/347, src/cadrumo/application/filing/record_renderer.py`.
- [ ] `P01.S14` - Make recargo de equivalencia and prorrata rows pass, with the recargo rate facts and the 303 election fields grounded in official text (lane CALC-IVA); `src/cadrumo/domain/iva, src/cadrumo/_data/registry/aeat/modelos/303`.
- [ ] `P01.S15` - Make an export after a granted verification always end in a written file or a typed refusal (lane LIFECYCLE, cause L1); `src/cadrumo/application/modelo/export.py`.
- [ ] `P01.S16` - Add a gate that fails when a modelo operation refusal or error code has no door or no served words, then fix what it finds (lane LIFECYCLE); `src/cadrumo/application/modelo, src/cadrumo/core/errors`.
- [ ] `P01.S17` - Run the full Python gate set green on a head where the persona table is green (lane INTEGRATOR); `justfile`.

### Phase `P02` - Deferred backend scope

Real backend work that the tree does not yet do, checked against the code on 2026-11-11. Not started until the first Phase is green and the coordinator says so.

- [ ] `P02.S18` - Support Impuesto sobre Sociedades for the sociedad-limitada persona: Modelo 200 and 202 calculation and export for every supported year; `src/cadrumo/_data/registry/aeat/modelos/200, src/cadrumo/_data/registry/aeat/modelos/202`.
- [ ] `P02.S19` - Add Modelo 840, 720, 721 and Patrimonio rows where a persona is obliged, or a typed not-supported refusal; `src/cadrumo/_data/registry/aeat/modelos/840, src/cadrumo/_data/registry/aeat/modelos/720, src/cadrumo/_data/registry/aeat/modelos/721`.
- [ ] `P02.S20` - Calculate and export successive corrections, complementaria and rectificativa, as persona table rows; `src/cadrumo/application/modelo/amendment_actions.py, dev/acceptance/persona_table`.
- [ ] `P02.S21` - Implement the per-activity estimation regime accepted on 2026-11-05; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/application/modelo/profile_derived_facts.py`.
- [ ] `P02.S22` - Serve every word, tax fact and capability from backend operations so that no surface authors them; `src/cadrumo/application`.
- [ ] `P02.S23` - Import datos fiscales and reconcile Modelo 100 credits against them, once the operator supplies a specimen; `src/cadrumo/adapters/inbound, src/cadrumo/application/live`.
- [ ] `P02.S24` - Finish moving login, session, access and custody authority from the tax package into the runtime package; `src/cadrumo/application/user_profile, src/cadrumo_runtime`.

### Phase `P03` - Desktop re-entry

Frozen since 2026-11-11. The native and desktop work that resumes, on the coordinator's or the operator's word, once the backend calculates correctly.

- [ ] `P03.S25` - Rebuild the desktop from a table-green head and verify the native commits and schema changes that landed unbuilt during the freeze; `native`.
- [ ] `P03.S26` - Delete the window's own word and fact maps as the backend serves them; `native/desktop/frontend/src`.
- [ ] `P03.S27` - Verify the on-demand local AI server natively and complete the llama.cpp default; `native/application/src/provisioning, native/manager`.
- [ ] `P03.S28` - Run every persona through the packaged application; `native/desktop/frontend/tests`.
- [ ] `P03.S29` - Verify live AEAT reads with the operator in an attended session; `src/cadrumo/adapters/outbound/aeat`.

## Parallelization

Within `P01` the Steps run in parallel across lanes whose file ownership is disjoint: the table itself (`S01` to `S03`), pagos fraccionados and retenciones (`S04` to `S06`), Modelo 100 (`S07` to `S11`), IVA (`S12` to `S14`) and the verify and export stages (`S15`, `S16`). Three orderings are hard: `S03` needs `S04`, because a quarter cannot be filed while first-quarter verification is blocked; `S08` needs `S03`, because box 0604 resolves only from filed Modelo 130 quarters; and `S17` comes last. One session merges every branch, first in, first out.

`P02` does not start before `P01` is complete, and `P03` not before the coordinator or the operator lifts the freeze. Inside `P02` the Steps are independent of each other except that `P02.S22` should precede `P03.S26`.

## Verification

- `P01`: every row of the persona table is green on one feature/tui head, for all nine personas, every modelo each is obliged to file, and every supported year; the committed table baseline records it; and the full Python gate set passes on that head.
- No Step of `P01` is checked on the evidence of a worktree run or a unit test alone. It is checked when the table shows its rows green after the change has landed.
- `P02`: each Step adds its rows to the persona table, or its own acceptance test where the table does not apply, and those pass on feature/tui.
- `P03`: the packaged application runs every persona with the same results as the table.

Review follows the framework cadence: at the close of each Phase and at plan close, against this plan and the three linked decisions.
