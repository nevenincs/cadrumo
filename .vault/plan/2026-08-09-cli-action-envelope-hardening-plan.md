---
tags:
  - '#plan'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_hash: 'sha256:3bd9220ef1eb90d915f8bf026b040f0a8df0d9262fcfd55f3374fde346e32ea7'
tier: L3
related:
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-research]]'
  - '[[2026-08-09-cli-action-envelope-hardening-reference]]'
---

# `cli-action-envelope-hardening` plan

## Description

## Steps

## Wave `W01` - Establish the fixed-point census and live denominator

Create the executable candidate ledger and exact live-surface denominator that every migration and closure claim depends on.

### Phase `W01.P01` - Candidate and adjudication inventory

Build the AST-backed candidate census, fixed-point alias expansion, and disposition contract.

- [ ] `W01.P01.S01` - Add an AST-backed census emitting stable candidate records keyed by path, enclosing symbol, role, alias, and action identity; `dev/cli_action_census.py`.
- [ ] `W01.P01.S02` - Add fixed-point vocabulary expansion and fail a closing pass that discovers a new semantic cluster; `dev/cli_action_census.py`.
- [ ] `W01.P01.S03` - Add the adjudicated disposition model with stale-exclusion detection and symbol-scoped reasons; `dev/cli_action_census_dispositions.py`.
- [ ] `W01.P01.S04` - Require every census candidate to carry exactly one current disposition; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.

### Phase `W01.P02` - Live surface reconciliation

Join callable leaves to schemas, manifest capabilities, policies, MCP exposure, and explicit exclusions by identity.

- [ ] `W01.P02.S05` - Expose live Click leaf identity and complete required-input metadata for action binding validation; `src/cadrumo/entrypoints/mcp/_input_schema.py`.
- [ ] `W01.P02.S06` - Build the identity reconciliation across leaves, schemas, manifest declarations, policies, and MCP exposure; `src/cadrumo/application/operator_surface/_manifest.py`.
- [ ] `W01.P02.S07` - Prove identity joins for callbacks, aliases, exclusions, and policy-filtered MCP leaves; `src/cadrumo/application/operator_surface/tests/test_contract.py`.

## Wave `W02` - Create the canonical action and precondition contract

Introduce application-owned verdicts and catalogue-backed action references before any producer migration begins.

### Phase `W02.P03` - Application-owned contract

Define strict condition, evidence, action, binding, conditionality, and no-recovery models and their catalogue.

- [ ] `W02.P03.S08` - Define immutable action references, bindings, precondition verdicts, evidence, conditionality, and no-recovery records; `src/cadrumo/application/operator_actions/_models.py`.
- [ ] `W02.P03.S09` - Define the canonical action catalogue without duplicating application guard predicates; `src/cadrumo/application/operator_actions/_catalogue.py`.
- [ ] `W02.P03.S10` - Prove strict action-model validation, catalogue uniqueness, binding sufficiency, and terminal outcomes; `src/cadrumo/application/operator_actions/tests/test_models.py`.

### Phase `W02.P04` - Schema-resolved envelope projection

Resolve typed actions against the live command surface and project them consistently through envelope, manifest, and MCP contracts.

- [ ] `W02.P04.S11` - Project resolved typed actions through notices while keeping localized text derived; `src/cadrumo/core/json_contract.py`.
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

- [ ] `W05.P08.S28` - Convert every adjudicated registered error default into an action reference or explicit no-recovery disposition; `src/cadrumo/core/errors/registry`.
- [ ] `W05.P08.S29` - Migrate every census-adjudicated production exception override to a typed action producer or grounded exclusion; `src/cadrumo`.
- [ ] `W05.P08.S30` - Prove registered error recovery resolves against the live command and input surface; `src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`.

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
- [ ] `W05.P10.S40` - Migrate live-read and AEAT adapter recovery producers with explicit safety dispositions; `src/cadrumo/application/live`.
- [ ] `W05.P10.S41` - Remove command identity from remaining adjudicated renderers and locale prose; `src/cadrumo/locales`.

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
