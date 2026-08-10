---
tags:
  - '#plan'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-10'
body_hash: 'sha256:4fe4925808516878d2fa454cc493f43c1f6b88af1e7d2d2f5fad8979faee0bb8'
tier: L3
related:
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-research]]'
  - '[[2026-08-09-cli-action-envelope-hardening-reference]]'
---

# `cli-action-envelope-hardening` plan

## Description

Implement the accepted application-owned precondition verdict and
schema-resolved action-chain architecture. The campaign starts by making its
blast radius executable, then introduces the canonical contract, migrates
complete producer-to-projection slices, and closes only through exact live
identity joins and real negative-recovery-retry observations. The related ADR,
research, and reference authorize every Wave. This VaultSpec lifecycle record
is intentionally not routed through the user-documentation pipeline.

## Steps

## Wave `W01` - Establish the fixed-point census and live denominator

Create the executable candidate ledger and exact live-surface denominator that every migration and closure claim depends on.

### Phase `W01.P01` - Candidate and adjudication inventory

Build the AST-backed candidate census, fixed-point alias expansion, and disposition contract.

- [x] `W01.P01.S01` - Add an AST-backed census emitting stable candidate records keyed by path, enclosing symbol, role, alias, and action identity; `dev/cli_action_census.py`.
- [x] `W01.P01.S02` - Add fixed-point vocabulary expansion and fail a closing pass that discovers a new semantic cluster; `dev/cli_action_census.py`.
- [x] `W01.P01.S03` - Add the adjudicated disposition model with stale-exclusion detection and symbol-scoped reasons; `dev/cli_action_census_dispositions.py`.
- [x] `W01.P01.S04` - Require every census candidate to carry exactly one current disposition; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
- [ ] `W01.P01.S49` - Expand migration Phases through the plan CLI with one exclusive Step per adjudicated producer cluster before execution; `.vault/plan/2026-08-09-cli-action-envelope-hardening-plan.md`.

### Phase `W01.P02` - Live surface reconciliation

Join callable leaves to schemas, manifest capabilities, policies, MCP exposure, and explicit exclusions by identity.

- [x] `W01.P02.S05` - Expose live Click leaf identity and complete required-input metadata for action binding validation; `src/cadrumo/entrypoints/mcp/_input_schema.py`.
- [x] `W01.P02.S06` - Build the identity reconciliation across leaves, schemas, manifest declarations, policies, and MCP exposure; `src/cadrumo/application/operator_surface/_manifest.py`.
- [x] `W01.P02.S07` - Prove identity joins for callbacks, aliases, exclusions, and policy-filtered MCP leaves; `src/cadrumo/application/operator_surface/tests/test_contract.py`.

## Wave `W02` - Create the canonical action and precondition contract

Introduce application-owned verdicts and catalogue-backed action references before any producer migration begins.

### Phase `W02.P03` - Application-owned contract

Define strict condition, evidence, action, binding, conditionality, and no-recovery models and their catalogue.

- [x] `W02.P03.S08` - Define immutable action references, bindings, precondition verdicts, evidence, conditionality, and no-recovery records; `src/cadrumo/application/operator_actions/_models.py`.
- [x] `W02.P03.S09` - Define the canonical action catalogue without duplicating application guard predicates; `src/cadrumo/application/operator_actions/_catalogue.py`.
- [x] `W02.P03.S10` - Prove strict action-model validation, catalogue uniqueness, binding sufficiency, and terminal outcomes; `src/cadrumo/application/operator_actions/tests/test_models.py`.

### Phase `W02.P04` - Schema-resolved envelope projection

Resolve typed actions against the live command surface and project them consistently through envelope, manifest, and MCP contracts.

- [x] `W02.P04.S11` - Project resolved typed actions through notices while keeping localized text derived; `src/cadrumo/core/json_contract.py`.
- [ ] `W02.P04.S12` - Carry resolved precondition actions in error envelopes and retire default suggestions as authority; `src/cadrumo/core/errors/_registry.py`.
- [ ] `W02.P04.S13` - Add manifest action-profile records that reference condition and action identities without predicates; `src/cadrumo/application/operator_surface/_models.py`.
- [ ] `W02.P04.S14` - Resolve catalogue actions against live command and input schemas and reject insufficient bindings; `src/cadrumo/application/operator_surface/_manifest.py`.
- [ ] `W02.P04.S15` - Use the shared action resolver for MCP action projection; `src/cadrumo/entrypoints/mcp/_input_schema.py`.

## Wave `W03` - Migrate the root profile and write-policy slice

Move the root guard and refusal boundary onto typed verdicts while preserving requested command identity and proving recovery.

### Phase `W03.P05` - Root guard verdicts and boundary transport

Replace root recovery prose, preserve leaf identity through pre-dispatch guards, and prove real profile recovery.

- [ ] `W03.P05.S16` - Replace storage write-policy recovery hints with typed failed-condition verdicts; `src/cadrumo/application/storage_write_policy.py`.
- [ ] `W03.P05.S17` - Preserve requested live leaf identity before root guards and project typed policy refusals; `src/cadrumo/entrypoints/cli/_common.py`.
- [ ] `W03.P05.S18` - Carry guarded command identity and verdict through the refusal boundary; `src/cadrumo/entrypoints/cli/_errors.py`.
- [ ] `W03.P05.S19` - Prove every storage policy condition identity evidence action status and binding set; `src/cadrumo/application/tests/test_storage_write_policy.py`.
- [ ] `W03.P05.S20` - Prove clean-root refusal recovery and retry through real CLI dispatch; `src/cadrumo/entrypoints/cli/tests/test_profile_guard_action_recovery.py`.

## Wave `W04` - Migrate workflow and modelo action chains

Replace persisted and rendered workflow continuations with application-owned typed action records and real recovery journeys.

### Phase `W04.P06` - Persisted workflow continuations

Remove untyped workflow next-action details and string-equality localization.

- [ ] `W04.P06.S21` - Replace persisted workflow next-action details with typed action and precondition records; `src/cadrumo/application/workflow/_models.py`.
- [ ] `W04.P06.S22` - Emit typed verdicts from workflow refusal branches; `src/cadrumo/application/workflow/_engine.py`.
- [ ] `W04.P06.S23` - Remove English string-equality recovery matching from work-run rendering; `src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py`.

### Phase `W04.P07` - Modelo leaf predicates and notices

Migrate calculate, verify, and file preconditions and their CLI projections with sufficient bindings.

- [ ] `W04.P07.S24` - Migrate adjudicated modelo work and verification predicates to typed verdicts; `src/cadrumo/application/modelo`.
- [ ] `W04.P07.S25` - Replace lifecycle suggestion construction with resolved typed action notices; `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`.
- [ ] `W04.P07.S26` - Replace unknown-revision and verification continuations with bound or explicitly conditional actions; `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py`.
- [ ] `W04.P07.S27` - Prove calculate verify and file negative-recovery-retry journeys; `src/cadrumo/entrypoints/cli/tests/test_modelo_action_recovery.py`.

## Wave `W05` - Migrate remaining action-authority clusters

Retire error-registry defaults and free-form operational guidance by complete producer-to-projection slices.

### Phase `W05.P08` - Error catalogue and exception overrides

Convert registered defaults and exception-level action overrides into catalogue references or explicit no-recovery outcomes.

- [ ] `W05.P08.S28` - Define the error-registry migration contract and catalogue projection; `src/cadrumo/core/errors/_registry.py`.
- [ ] `W05.P08.S29` - Fail when an adjudicated exception-override producer lacks an exclusive migration Step; `dev/cli_action_census_dispositions.py`.
- [ ] `W05.P08.S30` - Prove registered error recovery resolves against the live command and input surface; `src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`.
- [ ] `W05.P08.S50` - Migrate core error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_core.py`.
- [ ] `W05.P08.S51` - Migrate first application error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_application_part1.py`.
- [ ] `W05.P08.S52` - Migrate second application error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_application_part2.py`.
- [ ] `W05.P08.S53` - Migrate first domain error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_domain_part1.py`.
- [ ] `W05.P08.S54` - Migrate second domain error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_domain_part2.py`.
- [ ] `W05.P08.S55` - Migrate third domain error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_domain_part3.py`.
- [ ] `W05.P08.S56` - Migrate first adapter error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_adapters_part1.py`.
- [ ] `W05.P08.S57` - Migrate second adapter error-code defaults to catalogue action identities or explicit no-recovery outcomes; `src/cadrumo/core/errors/registry/_adapters_part2.py`.

### Phase `W05.P09` - Diagnostics overview and provisioning

Migrate high-density operational guidance and prove blank-state and readiness recovery.

- [ ] `W05.P09.S31` - Migrate overview next-step producers and blank-state advisories to typed actions; `src/cadrumo/application/overview`.
- [ ] `W05.P09.S32` - Migrate diagnostic remediation records to resolved actions or explicit no-recovery outcomes; `src/cadrumo/application/diagnostics.py`.
- [ ] `W05.P09.S33` - Migrate provisioning recovery guidance to typed conditions and actions; `src/cadrumo/application/provisioning.py`.
- [ ] `W05.P09.S34` - Render overview text and JSON from one typed action projection; `src/cadrumo/entrypoints/cli/_overview.py`.
- [ ] `W05.P09.S35` - Prove blank-state diagnostics and provisioning negative-recovery-retry journeys; `src/cadrumo/entrypoints/cli/tests/test_overview_provisioning_action_recovery.py`.

### Phase `W05.P10` - Remaining census-adjudicated producer clusters

Complete the auth, wizard, ledger, deadline, live, adapter, renderer, and locale slices named by the census.

- [ ] `W05.P10.S36` - Migrate authentication and session recovery predicates and actions; `src/cadrumo/application/auth`.
- [ ] `W05.P10.S37` - Migrate wizard status and next-step producers; `src/cadrumo/application/wizard`.
- [ ] `W05.P10.S38` - Migrate ledger findings lifecycle guards and recovery-action producers; `src/cadrumo/application/ledger`.
- [ ] `W05.P10.S39` - Migrate deadline recovery commands and overdue continuations; `src/cadrumo/domain/deadlines`.
- [ ] `W05.P10.S40` - Migrate live-read recovery producers with explicit safety dispositions; `src/cadrumo/application/live`.
- [ ] `W05.P10.S41` - Remove canonical command identity from locale prose and retain derived message templates; `src/cadrumo/locales`.
- [ ] `W05.P10.S58` - Migrate AEAT adapter recovery producers with explicit external-system safety dispositions; `src/cadrumo/adapters/outbound/aeat`.
- [ ] `W05.P10.S59` - Remove independently authored command identity from adjudicated CLI renderers; `src/cadrumo/entrypoints/cli`.
- [ ] `W05.P10.S60` - Migrate TUI recovery rendering to the shared resolved action projection; `src/cadrumo/adapters/inbound/tui`.
- [ ] `W05.P10.S61` - Migrate shipped agent harness action citations to canonical action identities; `src/cadrumo/_data/agent`.

## Wave `W06` - Prove action chains and close honestly

Generate the runtime matrix from production declarations, prove negative-recovery-retry behavior, reach a fixed point, and run the independent honesty review.

### Phase `W06.P11` - Runtime matrix and evaluator migration

Replace scenario-authored expectations with production-derived condition and action coverage.

- [ ] `W06.P11.S42` - Generate the leaf-condition-scenario matrix from live surface and production verdict declarations; `dev/agent_eval/_action_coverage.py`.
- [ ] `W06.P11.S43` - Replace scenario-owned expected actions with observed production condition and action assertions; `dev/agent_eval/_models.py`.
- [ ] `W06.P11.S44` - Dispatch negative cases validate bindings execute safe recovery and retry original leaves; `dev/agent_eval/_runner.py`.
- [ ] `W06.P11.S45` - Enforce the bidirectional declaration and observation join; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.

### Phase `W06.P12` - Fixed-point closure and campaign honesty

Require zero unclassified sites and exact declared-observed reconciliation before campaign closure.

- [ ] `W06.P12.S46` - Require a complete semantic and mechanical pass with no newly discovered action site or alias; `dev/cli_action_census.py`.
- [ ] `W06.P12.S47` - Fail closure on unclassified sites unresolved actions insufficient bindings missing proofs or ungrounded exclusions; `src/cadrumo/entrypoints/cli/tests/test_action_coverage_closure.py`.
- [ ] `W06.P12.S48` - Publish the final reconciliation and fresh-context honesty findings; `.vault/audit/2026-08-09-cli-action-envelope-hardening-audit.md`.

## Parallelization

Waves are ordered. Within W01, P01 and P02 may run concurrently after agreeing
on stable candidate and leaf identifiers. Within W02, P03 lands before P04.
W03 is the first complete migration slice and must be green before W04 or W05
begins. Within W04, P06 precedes P07 where modelo consumes persisted workflow
records. Within W05, P08, P09, and P10 may run in parallel with exclusive file
ownership after the latest fixed-point census assigns every candidate to one
slice. W06 begins only after all migration dispositions are closed.

Routine discovery, implementation, and verification are owned by Terra high
agents. Cross-cutting contracts, census machinery, live reconciliation, and
proof-matrix work are owned by Terra xhigh agents. Sol remains architecture
advisor and adjudicates only contract conflicts, evidence sufficiency, and
cross-Wave exceptions.

## Verification

- Feature-scoped RAG, AST, exact-search, and live-surface census completes one
  full iteration without discovering a new alias, producer, transformer,
  renderer, command form, or refusal site.
- Every candidate row has exactly one current disposition and every exclusion
  is keyed by symbol and enclosing function with a grounded reason.
- Every operator-callable leaf joins by identity to its result schema, input
  schema, manifest profile, policy classification, action profile, and declared
  MCP exposure or exclusion.
- Every reachable failed precondition emits a stable condition identity,
  evaluated evidence, and either a resolvable action with sufficient bindings
  or an explicit terminal, safety, or operator-decision outcome.
- Every declared actionable outcome joins to a real observation, and every
  observed actionable outcome joins to one declaration.
- Safe deterministic scenarios pass real negative dispatch, recovery dispatch,
  and retry; external and destructive boundaries carry explicit safety proof.
- Targeted owner tests, import-hygiene gates, strict typing, locale parity, and
  the relevant full CLI/MCP envelope suites pass without mocks, patches, skips,
  xfails, or tautological expected actions.
- A fresh-context Terra xhigh honesty review is persisted and every finding is
  closed or formally deferred with a follow-up reference before S48 is checked.
