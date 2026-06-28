---
tags:
  - '#plan'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
tier: L3
related:
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-research]]'
  - '[[2026-06-03-cli-workflow-redesign-epic-adr]]'
  - '[[2026-06-04-cli-workflow-redesign-epic-research]]'
---


<!-- RETIRED: W07, W08, W09, P13, P14, P15, P16, P22, P23, P24, P25, P26, P27, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S55, S56, S57, S58, S59, S60, S79, S80, S81, S82, S83, S84, S85, S86, S87, S88, S89, S90, S91, S92, S93, S94, S95, S96, S97, S98, S99, S100, S101, S102, S103, S104, S105, S106, S107, S108, S109, S110, S111, S112, S113, S114, S115, S116, S117, S118, S129, S131, S135, S138, S141, S144, S148, S152, S154, S155, S156, S157, S158, S159, S160, S161, S162, S163, S164, S165, S166, S167, S168, S169, S170, S171, S172, S173, S174, S175, S176, S177, S178, S179, S180, S181, S182, S183, S184 -->

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
selection, CLI command handlers, adjacent work-unit and revision
consumers, CLI payload rendering, locale messages, real-behavior CLI
tests, and the narrative docs that currently teach copy-paste ID
routing.

## Steps

## Wave `W01` - application selector and pointer semantics

Build the shared selector and revision-currentness contract before any CLI command depends on natural-key addressing.

### Phase `W01.P01` - build the application selector boundary

Create the shared application contract that resolves operator-visible filing targets before any CLI command creates or selects internal work-unit identity.

- [x] `W01.P01.S01` - add typed selector request result ambiguity and error objects; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P01.S02` - implement active-bucket and explicit-bucket resolution for modelo work selectors; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P01.S03` - implement visible-target-first work-unit lookup by bucket modelo filing year and period; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P01.S04` - implement explicit work-unit ID validation against supplied natural-key flags; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P01.S05` - implement registry revision conflict refusal before exact-target creation; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P01.S06` - export the selector boundary from the modelo application package; `src/aeat/application/modelo/__init__.py`.
- [x] `W01.P01.S07` - cover absent existing discarded ambiguous and revision-conflict work-unit resolution; `src/aeat/application/modelo/test_selectors.py`.

### Phase `W01.P02` - define revision selector semantics and pointer correctness

Make calculation revision defaults command-specific and close current-pointer gaps so later commands operate on the revision the user just produced or selected.

- [x] `W01.P02.S08` - add command-specific filed current and exportable calculation revision selector operations; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P02.S09` - advance current calculation pointers when duplicate draft revisions are reused; `src/aeat/application/modelo/_revision_persistence.py`.
- [x] `W01.P02.S10` - preserve filed and current filing pointer persistence invariants; `src/aeat/application/modelo/_revision_persistence.py`.
- [x] `W01.P02.S11` - cover current latest-draft latest-verified filed and explicit revision selection; `src/aeat/application/modelo/test_selectors.py`.
- [x] `W01.P02.S12` - cover duplicate calculation revision current-pointer behavior; `src/aeat/application/modelo/test_file_flow.py`.
- [x] `W01.P02.S13` - cover exportable revision preference without arbitrary latest fallback; `src/aeat/application/modelo/test_export.py`.

## Wave `W02` - CLI lifecycle and discovery

Wire the tested selector contract into the common operator lifecycle and discovery surfaces without widening raw-ID exposure.

### Phase `W02.P03` - expose readable work discovery payloads

Give list, status, and revisions surfaces enough human-readable state to explain what the resolver selected or why it refused.

- [x] `W02.P03.S14` - add current filed and filing pointer fields to work-unit CLI payloads; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W02.P03.S15` - render work-unit list rows with registry revision current revision filed state and short IDs; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P03.S16` - allow work status to resolve a natural filing target; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P03.S17` - allow work revisions to resolve a natural filing target; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P03.S18` - cover natural-key list status and revisions discovery output; `src/aeat/entrypoints/cli/test_modelo_work_ux.py`.

### Phase `W02.P08` - wire provisioning and duplicate prevention commands

Make provisioning resume one active visible-target work unit and refuse conflicting active workspaces before calculation begins.

- [x] `W02.P08.S19` - make work create idempotently resume an existing visible-target work unit; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W02.P04` - wire calculate verify and file lifecycle commands

Wire command-specific revision defaults into calculate verify and file after provisioning and discovery resolution are stable.

- [x] `W02.P04.S20` - allow work calculate to accept modelo year and period instead of a positional work-unit ID; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P04.S21` - allow work verify to accept modelo year period and a revision selector; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P04.S22` - allow work file to default to the current verified-complete revision under a natural target; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W02.P09` - wire export and end-to-end lifecycle assertions

Make export select filed and verified-complete revisions through the selector contract and prove the end-to-end lifecycle refusal behavior.

- [x] `W02.P09.S23` - allow modelo export to default to filed then current verified-complete revision under a natural target; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P09.S24` - cover the basic Modelo 130 lifecycle without copied IDs; `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`.
- [x] `W02.P09.S25` - cover refusal when a visible target has conflicting active registry revisions; `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`.
- [x] `W02.P09.S26` - cover export defaults for filed verified and ambiguous revision states; `src/aeat/entrypoints/cli/test_modelo_export_verb.py`.

## Wave `W03` - adjacent command compatibility audit

Classify every nearby work-unit or calculation-revision consumer as natural-key now exact-ID advanced only or deferred with a documented rationale.

### Phase `W03.P12` - preserve exact-ID compatibility and help rendering

Keep raw IDs as advanced exact-addressing inputs while retiring stale help that makes them the common operator path.

- [x] `W03.P12.S27` - keep positional work-unit and calculation-revision IDs as advanced exact addressing inputs; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P12.S28` - cover ID type hints and stale positional-ID help replacement in CLI output tests; `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py`.

### Phase `W03.P10` - classify adjacent work-unit commands

Decide which nearby work-unit commands join the natural-key first slice and which remain exact-ID advanced surfaces with documented rationale.

- [x] `W03.P10.S43` - record the adjacent command and internal service classification matrix covering application services CLI payloads help locales docs and exact-ID escape hatches; `.vault/exec/2026-06-04-modelo-addressing-ux`.
- [x] `W03.P10.S44` - classify and implement the work rename addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P10.S45` - classify and implement the work discard addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P10.S46` - classify and implement the work history addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P10.S47` - classify and implement the work compare-taxation addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P10.S48` - classify and implement the work amend addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W03.P11` - classify adjacent revision and modelo commands

Decide how adjacent calculation-revision and modelo-level consumers avoid accidental continued ID leakage in operator workflows.

- [x] `W03.P11.S49` - classify and implement the work revision addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P11.S50` - classify and implement the modelo reconcile addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P11.S51` - classify and implement the modelo reconcile-from-justificante addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P11.S52` - classify and implement the modelo project addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P11.S53` - classify and implement the modelo compare addressing decision; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P11.S54` - cover adjacent command internal service and selector enrollment decisions with focused regression tests; `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`.

## Wave `W04` - documentation reference and locales

Update user-facing docs generated reference help text and localization only after behavior and compatibility decisions are explicit.

### Phase `W04.P05` - localize natural-key operator guidance

Render resumed work ambiguity conflict and selector guidance in each supported locale without reintroducing raw-ID routing as the normal workflow.

- [x] `W04.P05.S61` - inventory stale localized help and operator guidance that routes common workflows through raw IDs; `src/aeat/locales`.
- [x] `W04.P05.S62` - add English messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/en.yml`.
- [x] `W04.P05.S63` - add Spanish messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/es.yml`.
- [x] `W04.P05.S64` - add Catalan messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/ca.yml`.
- [x] `W04.P05.S65` - add Hungarian messages for resumed work ambiguity conflicts and selector refusals; `src/aeat/locales/hu.yml`.
- [x] `W04.P05.S66` - cover retired ID-routing help payload metadata and natural-key guidance in CLI output tests; `src/aeat/entrypoints/cli/test_modelo_work_ux.py`.

### Phase `W04.P06` - update user documentation after tested behavior lands

Replace copy-paste ID routing in narrative docs only after the implementation is backed by real-behavior tests and live CLI help.

- [x] `W04.P06.S67` - rewrite the tutorial lifecycle path around natural-key modelo work commands; `docs/tutorials/index.md`.
- [x] `W04.P06.S68` - rewrite the getting-started lifecycle path around natural-key modelo work commands; `docs/getting-started.md`.
- [x] `W04.P06.S69` - rewrite the quickstart lifecycle path around natural-key modelo work commands; `docs/how-to/quickstart.md`.
- [x] `W04.P06.S70` - rewrite the Modelo 303 how-to lifecycle path around natural-key modelo work commands; `docs/how-to/modelo-303.md`.
- [x] `W04.P06.S71` - rewrite the Modelo 390 how-to lifecycle path around natural-key modelo work commands; `docs/how-to/modelo-390.md`.
- [x] `W04.P06.S72` - audit the reconciliation workflow and document natural-key or exact-ID rationale; `docs/how-to/reconcile.md`.
- [x] `W04.P06.S73` - update the filing spine explanation for work units revisions current pointers and selectors; `docs/how-to/filing-spine.md`.
- [x] `W04.P06.S74` - regenerate the CLI reference after command signature changes; `docs/cli`.

## Wave `W06` - CLI boundary and monolith mitigation

Audit and mitigate CLI business-logic leakage and monolithic command modules introduced or exposed by the modelo addressing work. CLI modules must parse operator input call backend application services and render typed output only; business decisions tax rules persistence selection policies and workflow orchestration must live in backend library modules. Monolithic Python files and high-complexity command handlers must be decomposed into bounded modules with enforceable guards.

### Phase `W06.P18` - audit CLI boundary and monolith risk

Inventory every CLI module and modelo command handler for business logic leakage file size command density function complexity nesting and backend-service bypasses before further natural-key implementation is considered complete.

- [x] `W06.P18.S127` - inventory CLI module size command density function length nesting and complexity risk for every entrypoint module; `src/aeat/entrypoints/cli`.
- [x] `W06.P18.S128` - run exact rg audit for tax calculation persistence workflow registry and selection logic inside CLI command modules; `rg CLI business-logic leakage audit`.
- [x] `W06.P18.S130` - run semantic vaultspec-rag audit for CLI business-rule reinvention and backend-service bypasses; `vaultspec-rag CLI boundary audit`.
- [x] `W06.P18.S132` - persist CLI command classification matrix separating parsing rendering backend calls and business decisions; `.vault/exec/2026-06-04-modelo-addressing-ux`.
- [x] `W06.P18.S133` - map every identified CLI business decision to an application-layer backend service home before extraction; `src/aeat/application`.

### Phase `W06.P19` - relocate CLI business logic to backend services

Move business declarations calculations target resolution defaulting policies persistence decisions reconciliation export project and compare orchestration out of CLI command bodies and into application-layer service functions with real-behavior tests.

- [x] `W06.P19.S134` - extract modelo natural-key lifecycle orchestration from CLI command bodies into application service functions; `src/aeat/application/modelo`.
- [x] `W06.P19.S136` - relocate revision selector defaulting exportability filing and verification policy out of CLI helpers into backend services; `src/aeat/application/modelo`.
- [x] `W06.P19.S137` - relocate reconcile export project compare and taxation command orchestration into backend application services; `src/aeat/application/modelo`.
- [x] `W06.P19.S139` - replace CLI command bodies with parse call backend render flow and no business-rule branching; `src/aeat/entrypoints/cli`.

### Phase `W06.P20` - decompose monolithic CLI modules

Split monolithic CLI files into bounded command-group modules and shared rendering helpers so command functions stay shallow readable and limited to input parsing backend invocation and output rendering.

- [x] `W06.P20.S140` - split the monolithic modelo CLI module into bounded command-group modules without changing public command names; `src/aeat/entrypoints/cli`.
- [x] `W06.P20.S142` - move shared modelo CLI parsing rendering and envelope helpers into focused support modules without business decisions; `src/aeat/entrypoints/cli`.
- [x] `W06.P20.S143` - add static architecture guard preventing CLI modules from importing domain internals or bypassing application facades; `src/aeat/entrypoints/cli/test_architecture_boundaries.py`.
- [x] `W06.P20.S145` - add static size and complexity guard forbidding monolithic Python files and overgrown CLI command functions; `src/aeat/entrypoints/cli/test_cli_module_size.py`.
- [x] `W06.P20.S146` - cover extracted backend services and decomposed CLI modules with real-behavior regression tests; `src/aeat/application/modelo src/aeat/entrypoints/cli`.

### Phase `W06.P21` - verify CLI boundary and decomposition gates

Prove through exact search semantic search static guards focused tests and feature-surface gates that CLI modules no longer host business logic and no monolithic Python file remains accepted in the changed modelo CLI surface.

- [x] `W06.P21.S147` - run final exact rg audit proving changed CLI modules contain no business-rule declarations or raw backend bypasses; `rg CLI boundary closure audit`.
- [x] `W06.P21.S149` - run final semantic vaultspec-rag audit proving CLI is a backend consumer not a business-logic reinventor; `vaultspec-rag CLI boundary closure audit`.
- [x] `W06.P21.S150` - run static size complexity and architecture boundary guards for CLI and modelo addressing surfaces; `src/aeat/entrypoints/cli src/aeat/application/modelo`.
- [x] `W06.P21.S151` - run focused application and CLI regression tests after extraction and decomposition; `src/aeat/application/modelo src/aeat/entrypoints/cli`.
- [x] `W06.P21.S153` - persist CLI boundary monolith mitigation closure evidence and residual risk matrix; `.vault/exec/2026-06-04-modelo-addressing-ux`.

## Wave `W05` - verification gates

Run focused application CLI documentation and feature-surface gates against the revised L3 scope.

### Phase `W05.P07` - run focused verification gates

Validate the selector, lifecycle, documentation, and feature-surface behavior with targeted checks before the plan can close.

- [x] `W05.P07.S75` - run focused application selector and lifecycle tests; `src/aeat/application/modelo`.
- [x] `W05.P07.S76` - run focused modelo CLI natural-key and legacy-ID tests; `src/aeat/entrypoints/cli`.
- [x] `W05.P07.S77` - run docs conformance for updated narrative and generated CLI surfaces; `docs conformance lane`.
- [x] `W05.P07.S78` - run the feature surface gate for changed modelo addressing files; `feature-surface-gate`.

### Phase `W05.P17` - run raw-ID leakage and semantic coverage gates

Close the plan only after exact-match semantic and file-discovery audits prove every raw work-unit or calculation-revision operator surface is standardized or intentionally retained as exact-ID advanced behavior.

- [x] `W05.P17.S119` - run exact raw-ID leakage audit over source locales and docs; `rg raw-id leakage audit`.
- [x] `W05.P17.S120` - run semantic raw-ID leakage audit over source locales and docs; `vaultspec-rag`.
- [x] `W05.P17.S121` - run file-discovery blast-radius audit for modelo work and revision surfaces; `fd blast-radius inventory`.
- [x] `W05.P17.S122` - persist the final blast-radius classification matrix and closure evidence; `.vault/exec/2026-06-04-modelo-addressing-ux`.
- [x] `W05.P17.S123` - verify internal service coverage for action export reconcile history taxation result-summary and state-projection ID linkage; `src/aeat/application`.
- [x] `W05.P17.S124` - verify external CLI abstraction coverage for modelo command handlers payload schemas and work group help; `src/aeat/entrypoints/cli`.
- [x] `W05.P17.S125` - verify narrative and generated documentation coverage for all raw-ID workflow references; `docs`.
- [x] `W05.P17.S126` - verify locale and translation guard coverage for all raw-ID workflow references; `src/aeat/locales`.

## Parallelization

`W01` must land before CLI command wiring because every visible-target
command depends on the shared selector and revision-default contract.
Within `W02`, provisioning and discovery can proceed in parallel after
`W01`, while calculate verify file and export should wait for the
selector invariants they exercise. `W03` can classify adjacent commands
in parallel with `W02` implementation work, but any compatibility
decision that changes command signatures must settle before `W04`
updates generated reference docs, locale strings, or narrative guides.
`W04` documentation changes must use the documentation workflow and must
wait until real-behavior CLI tests prove the common lifecycle path no
longer requires manually copying work-unit or calculation-revision IDs.
`W06` runs before the first closure whenever modelo addressing work
touches CLI command bodies, because the CLI must stay a consumer of
backend application services rather than a business-logic host. `W05`
records the original closure gates after `W06` mitigation.

## Verification

The plan is complete when every Step is closed, the plan status reports
six waves with no open structural validation findings, focused
application and CLI tests prove visible-target-first resolution,
duplicate prevention, revision selector defaults, export selection,
adjacent-command compatibility decisions, and exact-ID compatibility,
localized operator messages render clearly without stale ID-routing
guidance, the affected documentation no longer teaches pasted-ID routing
for the common path, W06 proves changed CLI modules consume backend
addressing helpers instead of reinventing resolver policy, and the
feature surface gate reports only relevant pass/fail results for this
change set.
