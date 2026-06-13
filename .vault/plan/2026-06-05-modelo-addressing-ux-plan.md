---
tags:
  - '#plan'
  - '#modelo-addressing-ux'
date: '2026-06-05'
modified: '2026-06-05'
tier: L3
related:
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-research]]'
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
  - '[[2026-06-04-modelo-addressing-ux-code-review-audit]]'
---

# `modelo-addressing-ux` `modelo CLI decomposition continuous plan` plan

## Description

This plan is the continuous execution track for decomposing the legacy modelo CLI root and completing natural-key work addressing under the accepted modelo-addressing-ux ADR. The operating principle is that CLI modules are transports and consumers of backend application services; they must not own business policy, registry authority, calculation behavior, work-unit selection policy, or revision semantics.

The plan deliberately sequences work in the order requested for execution while adding an explicit centralized-addressing baseline before further command rewrites. Modelo lifecycle extraction and calculation extraction must consume shared application helpers for model-period work selection, revision picks, and exact-id projection instead of recreating that policy in CLI modules. Resume exact UUID or exact work identifier support is preserved as legacy compatibility, while the normal operator-facing path must support modelo year period addressing and command-specific revision selectors.

Any design question not already authorized by the related ADR, research, prior plan, or code-review audit must stop at an ADR gate before implementation. This includes hidden state, new legally meaningful selector axes, or any change that alters how ambiguous filing targets are resolved.

## Wave `W01` - continuous decomposition control plane

Establish the continuous control plane for decomposing the legacy modelo CLI root while preserving the accepted natural-key addressing ADR and requiring new ADR coverage for any interface decision not already authorized.

### Phase `W01.P01` - baseline and ADR gate

Freeze the current decomposition baseline and define when future implementation slices must stop for research and ADR work instead of changing interface behavior directly.

- [x] `W01.P01.S01` - inventory current modelo CLI root size command groups helper groups and private backend touchpoints; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P01.S02` - run semantic discovery for remaining modelo CLI decomposition seams and residual business logic; `vaultspec-rag modelo CLI decomposition audit`.
- [x] `W01.P01.S03` - persist the continuous decomposition baseline and extraction order; `.vault/exec/2026-06-05-modelo-addressing-ux`.
- [x] `W01.P01.S04` - classify every proposed interface change as accepted ADR covered or new ADR required before implementation; `.vault/exec/2026-06-05-modelo-addressing-ux`.

### Phase `W01.P02` - guardrail hardening

Strengthen regression guards so the legacy root cannot grow new boundary debt while extraction proceeds over multiple execution sessions.

- [x] `W01.P02.S05` - add a frozen private import baseline for the legacy modelo CLI root; `src/aeat/entrypoints/cli/test_architecture_boundaries.py`.
- [x] `W01.P02.S06` - add a frozen registry authority access baseline for the legacy modelo CLI root; `src/aeat/entrypoints/cli/test_architecture_boundaries.py`.
- [x] `W01.P02.S07` - tighten module size budgets after each successful extraction slice; `src/aeat/entrypoints/cli/test_cli_module_size.py`.
- [x] `W01.P02.S08` - verify the decomposition guards fail on newly introduced private backend bypasses; `src/aeat/entrypoints/cli/test_architecture_boundaries.py`.

### Phase `W01.P11` - central addressing contract baseline

Define the shared modelo addressing contract before any remaining CLI extraction or resume work so model-period selectors exact identifiers revision picks and visible target projections are resolved in one application surface.

- [x] `W01.P11.S40` - inventory every remaining resolver that maps modelo period work-unit id calculation-revision id workflow-run id registry revision selector or exact-id target; `rg resolver duplication inventory`.
- [x] `W01.P11.S41` - define typed modelo addressing contracts for visible filing targets exact work-unit targets revision picks resolved work projections and resolved revision projections; `src/aeat/application/modelo/_work_addressing.py`.

### Phase `W01.P12` - bidirectional addressing facade implementation

Implement and test a backend facade that maps visible modelo filing targets revision picks and exact ids to work-unit and calculation-revision identities in both operator and support directions.

- [x] `W01.P12.S42` - implement visible filing target to work-unit id resolution and exact work-unit id to visible filing target projection through one application facade; `src/aeat/application/modelo/_work_addressing.py`.
- [x] `W01.P12.S43` - implement centralized revision-pick resolution from modelo year period selector explicit revision ids and command-specific defaults to calculation revision id and owning work-unit id; `src/aeat/application/modelo/_selectors.py`.
- [x] `W01.P12.S44` - export the centralized addressing facade from the modelo application package and route application callers through that public surface; `src/aeat/application/modelo/__init__.py`.
- [x] `W01.P12.S45` - cover visible-target exact-id and revision-pick round trips through the centralized addressing facade with real repositories; `src/aeat/application/modelo/test_work_addressing.py`.

## Wave `W02` - modelo lifecycle surface extraction

Extract the modeller or modelo lifecycle operating surface from the legacy root first so create list status rename discard readiness and discovery commands become bounded transports over application services.

### Phase `W02.P03` - work lifecycle command registrar

Move active filing workspace lifecycle commands into a focused command module without changing public command names or natural-key behavior.

- [x] `W02.P03.S09` - extract work create list status rename and discard registration into a focused module; `src/aeat/entrypoints/cli/_modelo_work_lifecycle_cli.py`.
- [x] `W02.P03.S10` - replace legacy lifecycle command bodies with registrar mounting only; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P03.S11` - move lifecycle rendering helpers into shared rendering support where they are transport only; `src/aeat/entrypoints/cli/_modelo_rendering.py`.
- [x] `W02.P03.S12` - cover lifecycle extraction with real natural-key CLI regressions; `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`.

### Phase `W02.P04` - modelo discovery command registrar

Move registry-readiness and discovery commands behind focused modules or application facades while refusing new registry authority bypasses in the CLI root.

- [x] `W02.P04.S13` - extract modelo readiness command registration into a focused module; `src/aeat/entrypoints/cli/_modelo_readiness_cli.py`.
- [x] `W02.P04.S14` - extract bindings casillas and registry query command registration into focused modules; `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`.
- [x] `W02.P04.S15` - move remaining registry authority query construction behind application facades or recorded ADR debt; `src/aeat/application/modelo`.
- [x] `W02.P04.S16` - cover discovery extraction with CLI shape and readiness regressions; `src/aeat/entrypoints/cli`.

## Wave `W03` - work calculation extraction

Extract the work calculation operating surface second so the long calculate command becomes a bounded transport while calculation policy and input normalization stay in backend services.

### Phase `W03.P05` - calculate command registrar

Move the large work calculate command into a dedicated registrar and keep the legacy root free of calculation-specific option and rendering bulk.

- [x] `W03.P05.S17` - extract work calculate registration into a focused command module; `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`.
- [x] `W03.P05.S18` - replace the legacy work calculate body with registrar mounting only; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P05.S19` - move calculate transport parsing helpers that are not business policy into support module; `src/aeat/entrypoints/cli/_modelo_cli_support.py`.
- [x] `W03.P05.S20` - preserve backend ownership of casilla normalization row validation binding split and shortcut application; `src/aeat/application/modelo/_calculate_input.py`.

### Phase `W03.P06` - calculate regression and budget closure

Prove calculation extraction preserves the natural-key workflow and shrinks the legacy root budgets without weakening row or registry behavior.

- [x] `W03.P06.S21` - cover calculate extraction with natural-key and real calculation CLI regressions; `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`.
- [x] `W03.P06.S22` - cover row flag parsing persistence and rendering after calculate extraction; `src/aeat/entrypoints/cli/test_work_calculate_row_flag.py`.
- [x] `W03.P06.S23` - lower the frozen work calculate command budget after extraction; `src/aeat/entrypoints/cli/test_cli_module_size.py`.
- [x] `W03.P06.S24` - run exact and semantic audits for calculate business logic absence in CLI modules; `rg and vaultspec-rag calculate boundary audit`.

## Wave `W04` - work resume natural-key and legacy exact-id interface

Implement the resume interface last so it conforms to the accepted natural-key CLI intent while preserving UUID or exact-id compatibility as a legacy escape hatch.

### Phase `W04.P07` - resume interface design gate

Confirm the resume interface is covered by the accepted ADR or stop for a new ADR before changing user-visible semantics.

- [x] `W04.P07.S25` - record the resume interface contract for natural-key selectors and legacy exact-id support; `.vault/exec/2026-06-05-modelo-addressing-ux`.
- [x] `W04.P07.S26` - open a new ADR before implementation if resume requires hidden state or a new legally meaningful selector axis; `.vault/adr`.
- [x] `W04.P07.S27` - define resume ambiguity refusal and candidate guidance for modelo year period addressing; `src/aeat/application/workflow`.

### Phase `W04.P08` - resume implementation

Add natural-key resume selection while keeping exact UUID or work identifier resume as documented legacy compatibility.

- [x] `W04.P08.S28` - extend workflow resume resolution to accept modelo year period and selector inputs; `src/aeat/application/workflow`.
- [x] `W04.P08.S29` - update work resume CLI to support natural-key flags and legacy exact-id target; `src/aeat/entrypoints/cli/_modelo_work_runs_cli.py`.
- [x] `W04.P08.S30` - reuse shared exact-id shape validation for the legacy resume escape hatch; `src/aeat/entrypoints/cli/_modelo_cli_support.py`.
- [x] `W04.P08.S31` - cover natural-key resume exact-id resume and ambiguity refusal with real CLI tests; `src/aeat/entrypoints/cli/test_work_resume.py`.
- [x] `W04.P08.S46` - route work resume modelo year period and revision selector resolution through the centralized modelo addressing facade before workflow-run lookup; `src/aeat/application/workflow`.
- [x] `W04.P08.S47` - project resumable workflow runs back to modelo visible filing targets and short exact identifiers for operator guidance; `src/aeat/entrypoints/cli/_modelo_work_runs_cli.py`.

## Wave `W05` - continuous verification and handoff

Close each long-running decomposition slice with evidence so multi-day work remains auditable and new architecture questions are routed back through VaultSpec ADRs.

### Phase `W05.P09` - slice verification cadence

Define repeatable verification gates for every extraction slice instead of relying on a single final pass.

- [x] `W05.P09.S32` - run plan status and check after every completed extraction slice; `.vault/plan/2026-06-05-modelo-addressing-ux-plan.md`.
- [x] `W05.P09.S33` - persist a step record for every completed decomposition step; `.vault/exec/2026-06-05-modelo-addressing-ux`.
- [x] `W05.P09.S34` - run focused CLI and application regressions for each touched command group; `src/aeat/entrypoints/cli src/aeat/application`.
- [x] `W05.P09.S35` - run architecture size exact-search and semantic-search gates after each wave; `src/aeat/entrypoints/cli`.

### Phase `W05.P10` - final closure review

Finish the continuous decomposition plan only when the legacy root has shrunk and residual risks are explicitly tracked or closed.

- [x] `W05.P10.S36` - persist final residual risk matrix for remaining legacy CLI debt; `.vault/exec/2026-06-05-modelo-addressing-ux`.
- [x] `W05.P10.S37` - run vaultspec code review over the full decomposition surface; `.vault/audit`.
- [x] `W05.P10.S38` - update follow-up ADR queue for unresolved architecture questions; `.vault/adr`.
- [x] `W05.P10.S39` - validate the plan and report completion or remaining open steps; `.vault/plan/2026-06-05-modelo-addressing-ux-plan.md`.

### Phase `W05.P13` - centralized addressing closure guards

Prove the new addressing facade is the only policy surface for modelo visible-target exact-id and revision-pick resolution across CLI modules and adjacent command groups before final handoff.

- [x] `W05.P13.S48` - rewire calculate verify file export project compare reconcile history and resume command modules to consume centralized addressing results instead of local selector branching; `src/aeat/entrypoints/cli`.
- [x] `W05.P13.S49` - add a static guard forbidding CLI-local raw-id regexes direct selector policy and duplicated work-address parsing outside centralized helpers; `src/aeat/entrypoints/cli/test_architecture_boundaries.py`.
- [x] `W05.P13.S50` - run exact audit for duplicated raw-id regexes local selector branching legacy ID-first resume text and decentralized revision-pick handling; `rg centralized-addressing closure audit`.
- [x] `W05.P13.S51` - run semantic vaultspec-rag audit proving CLI and workflow surfaces consume centralized addressing instead of reinventing resolver policy; `vaultspec-rag centralized-addressing closure audit`.
- [x] `W05.P13.S52` - run focused application CLI work resume export project compare reconcile and docs conformance tests after centralized addressing migration; `src/aeat/application/modelo src/aeat/entrypoints/cli docs`.

## Steps

The canonical Step rows are the W01 through W05 hierarchy above. This section is intentionally kept as a pointer so future executors do not append duplicate rows outside the validated L3 structure.

## Parallelization

Waves are ordered by default. W01 must run first because it establishes the baseline, ADR gate, semantic discovery obligation, guardrails, and centralized addressing facade that prevent the legacy root from growing while extraction proceeds. W02 then extracts the modelo lifecycle and discovery surface through those shared helpers. W03 follows for calculation. W04 follows for resume because the resume contract depends on stable lifecycle, calculation, and centralized revision-pick semantics. W05 is both a recurring verification cadence and the final closure track, including explicit guards that adjacent commands do not recreate raw-id parsing or selector policy locally.

Within a wave, phases may run in parallel only when they do not edit the same command module, backend facade, test file, or plan record. Parallel agents must coordinate through Step records and must never perform competing identifier-affecting plan edits by hand.

Architecture or interface questions that are not already covered by the accepted ADR are not parallel implementation work. They must be routed into the ADR pipeline first, then returned to this plan or a successor plan after acceptance.

## Verification

The plan is complete only when every Step in W01 through W05 is closed and `vaultspec-core vault plan check` passes for this file.

Each extraction slice must leave evidence in the exec vault, run direct `rg` or `fd` discovery plus semantic `vaultspec-rag` discovery for the touched surface, and pass focused real-behavior tests over the changed CLI and application modules.

The final closure must prove that the legacy modelo CLI root has shrunk, remaining business logic is either relocated to backend services or explicitly tracked as residual debt, natural-key modelo work addressing remains the normal operator path, centralized application helpers own model-period work resolution revision-pick resolution and exact-id projection, raw UUID or exact-id resume remains legacy-compatible, and unresolved architecture questions are represented in a follow-up ADR queue.
