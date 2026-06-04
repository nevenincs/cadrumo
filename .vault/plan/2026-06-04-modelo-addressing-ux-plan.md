---
tags:
  - '#plan'
  - '#modelo-addressing-ux'
date: '2026-06-04'
tier: L2
related:
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-research]]'
  - '[[2026-06-03-cli-workflow-redesign-epic-adr]]'
  - '[[2026-06-04-cli-workflow-redesign-epic-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `modelo-addressing-ux` implementation plan

Implement natural-key addressing for the modelo work CLI while preserving
content-addressed work units and calculation revisions as the internal
audit authority.

## Description

This plan implements the accepted visible-target-first modelo addressing
ADR. The common operator path should address a filing by active bucket,
modelo, filing year, and period. The application then resolves that
visible target to one active work unit, refuses ambiguity, and applies
command-specific calculation revision defaults for calculate, verify,
file, and export. Raw work-unit and calculation-revision IDs remain
available for audit, exact replay, and advanced support workflows.

The plan is grounded in vaultspec RAG discovery and direct code-site
review. The relevant implementation surfaces are the modelo application
actions, work-unit identity, calculation revision persistence, export
selection, CLI command handlers, CLI payload rendering, locale messages,
real-behavior CLI tests, and the narrative docs that currently teach
copy-paste ID routing.

## Steps

### Phase `P01` - build the application selector boundary

Create the shared application contract that resolves operator-visible filing targets before any CLI command creates or selects internal work-unit identity.

- [ ] `P01.S01` - add typed selector request result ambiguity and error objects; `src/aeat/application/modelo/_selectors.py`.
- [ ] `P01.S02` - implement active-bucket and explicit-bucket resolution for modelo work selectors; `src/aeat/application/modelo/_selectors.py`.
- [ ] `P01.S03` - implement visible-target-first work-unit lookup by bucket modelo filing year and period; `src/aeat/application/modelo/_selectors.py`.
- [ ] `P01.S04` - implement explicit work-unit ID validation against supplied natural-key flags; `src/aeat/application/modelo/_selectors.py`.
- [ ] `P01.S05` - implement registry revision conflict refusal before exact-target creation; `src/aeat/application/modelo/_selectors.py`.
- [ ] `P01.S06` - export the selector boundary from the modelo application package; `src/aeat/application/modelo/__init__.py`.
- [ ] `P01.S07` - cover absent existing discarded ambiguous and revision-conflict work-unit resolution; `src/aeat/application/modelo/test_selectors.py`.

### Phase `P02` - define revision selector semantics and pointer correctness

Make calculation revision defaults command-specific and close current-pointer gaps so later commands operate on the revision the user just produced or selected.

- [ ] `P02.S08` - add command-specific calculation revision selector operations; `src/aeat/application/modelo/_selectors.py`.
- [ ] `P02.S09` - advance current calculation pointers when duplicate draft revisions are reused; `src/aeat/application/modelo/_revision_persistence.py`.
- [ ] `P02.S10` - preserve filed pointers while making filed revision selection explicit; `src/aeat/application/modelo/_revision_persistence.py`.
- [ ] `P02.S11` - cover current latest-draft latest-verified filed and explicit revision selection; `src/aeat/application/modelo/test_selectors.py`.
- [ ] `P02.S12` - cover duplicate calculation revision current-pointer behavior; `src/aeat/application/modelo/test_file_flow.py`.
- [ ] `P02.S13` - cover exportable revision preference without arbitrary latest fallback; `src/aeat/application/modelo/test_export.py`.

### Phase `P03` - expose readable work discovery payloads

Give list, status, and revisions surfaces enough human-readable state to explain what the resolver selected or why it refused.

- [ ] `P03.S14` - add current filed and filing pointer fields to work-unit CLI payloads; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [ ] `P03.S15` - render work-unit list rows with registry revision current revision filed state and short IDs; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P03.S16` - allow work status to resolve a natural filing target; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P03.S17` - allow work revisions to resolve a natural filing target; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P03.S18` - cover natural-key list status and revisions discovery output; `src/aeat/entrypoints/cli/test_modelo_work_ux.py`.

### Phase `P04` - wire natural-key lifecycle commands

Allow the common work create, calculate, verify, file, and export path to use modelo, year, and period while preserving raw IDs as explicit exact-addressing escape hatches.

- [ ] `P04.S19` - make work create idempotently resume an existing visible-target work unit; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P04.S20` - allow work calculate to accept modelo year and period instead of a positional work-unit ID; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P04.S21` - allow work verify to accept modelo year period and a revision selector; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P04.S22` - allow work file to accept modelo year period and a revision selector; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P04.S23` - allow modelo export to accept modelo year period and a revision selector; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P04.S24` - cover the basic Modelo 130 lifecycle without copied IDs; `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`.
- [ ] `P04.S25` - cover refusal when a visible target has conflicting active registry revisions; `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`.
- [ ] `P04.S26` - cover export defaults for filed verified and ambiguous revision states; `src/aeat/entrypoints/cli/test_modelo_export_verb.py`.

### Phase `P05` - localize and preserve legacy compatibility

Keep existing ID-driven scripts working and render ambiguity, conflict, and selector errors in localized operator language.

- [ ] `P05.S27` - keep positional work-unit and calculation-revision IDs as exact addressing inputs; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P05.S28` - render ID type hints alongside the new natural-key guidance; `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py`.
- [ ] `P05.S29` - add English messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/en.yml`.
- [ ] `P05.S30` - add Spanish messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/es.yml`.
- [ ] `P05.S31` - add Catalan messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/ca.yml`.
- [ ] `P05.S32` - add Hungarian messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/hu.yml`.

### Phase `P06` - update user documentation after tested behavior lands

Replace copy-paste ID routing in narrative docs only after the implementation is backed by real-behavior tests and live CLI help.

- [ ] `P06.S33` - rewrite the tutorial lifecycle path around natural-key modelo work commands; `docs/tutorials/index.md`.
- [ ] `P06.S34` - rewrite the getting-started lifecycle path around natural-key modelo work commands; `docs/getting-started.md`.
- [ ] `P06.S35` - rewrite the quickstart lifecycle path around natural-key modelo work commands; `docs/how-to/quickstart.md`.
- [ ] `P06.S36` - update the filing spine explanation for work units revisions current pointers and selectors; `docs/how-to/filing-spine.md`.
- [ ] `P06.S37` - regenerate the CLI reference after command signature changes; `docs/cli`.

### Phase `P07` - run focused verification gates

Validate the selector, lifecycle, documentation, and feature-surface behavior with targeted checks before the plan can close.

- [ ] `P07.S38` - run focused application selector and lifecycle tests; `src/aeat/application/modelo`.
- [ ] `P07.S39` - run focused modelo CLI natural-key and legacy-ID tests; `src/aeat/entrypoints/cli`.
- [ ] `P07.S40` - run docs conformance for updated narrative and generated CLI surfaces; `docs conformance lane`.
- [ ] `P07.S41` - run the feature surface gate for changed modelo addressing files; `feature-surface-gate`.

## Parallelization

Application selector tests and selector implementation should land before
CLI verb wiring. Payload and read-only rendering can proceed in parallel
with the revision selector work after the selector result contract is
stable. Documentation must wait until the real-behavior CLI tests prove
the tutorial path no longer requires manual copying of work-unit or
calculation-revision IDs.

## Verification

The plan is complete when every Step is closed, focused application and
CLI tests prove visible-target-first resolution, duplicate prevention,
revision selector defaults, export selection, and legacy ID compatibility,
localized operator messages render clearly, the affected documentation no
longer teaches pasted-ID routing for the common path, and the feature
surface gate reports only relevant pass/fail results for this change set.
