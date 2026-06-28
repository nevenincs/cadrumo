---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---



# `cli-workflow-redesign` audit: `master plan rollout snapshot`

## Scope

The scope of this audit covers a comprehensive review of the active plans and rollout progress within the workspace under the `cli-workflow-redesign` campaign. A scan was conducted across the `.vault/plan/` directory for May 2026 documents to compile an inventory of checked versus unchecked steps, determine the exact state of the CLI Workflow Redesign Epic Master Plan, and identify the outstanding tasks remaining to achieve complete epic closure.

## Findings

### 1. Overall Campaign Execution Status
An audit of the May 2026 execution plan corpus shows substantial progress toward completing the core refactoring of the entrypoint and command handling layers. 

The campaign is characterized by:
- A total of 258 Architecture Decision Records (ADRs) rolled out to govern calculations, boundaries, persistence, and workflows.
- High completion rates across the major campaign plans, with several critical integration and schema-hardening tracks fully verified.

### 2. May 2026 Plan Inventory and Status Mapping
The complete set of execution plans active or created during May 2026 is mapped below by completion percentage:

| Plan Document | Checked Steps | Total Steps | Completion | Status |
| :--- | :--- | :--- | :--- | :--- |
| `2026-05-13-cli-workflow-redesign-epic-plan.md` | 2302 | 2353 | 97.8% | In-Flight (51 steps open) |
| `2026-05-13-cli-workflow-redesign-config-repair-shape-plan.md` | 44 | 44 | 100.0% | Completed |
| `2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan.md` | 10 | 33 | 30.3% | In-Flight (23 steps open) |
| `2026-05-15-corpus-registry-packaging-plan.md` | 66 | 66 | 100.0% | Completed |
| `2026-05-16-linkage-design-audit-plan.md` | 25 | 25 | 100.0% | Completed |
| `2026-05-16-profile-lifecycle-cli-plan.md` | 47 | 64 | 73.4% | In-Flight (17 steps open) |
| `2026-05-16-resource-management-api-plan.md` | 96 | 96 | 100.0% | Completed |
| `2026-05-18-profile-lifecycle-cli-plan.md` | 2 | 52 | 3.8% | In-Flight (50 steps open) |
| `2026-05-18-schema-hardening-plan.md` | 101 | 101 | 100.0% | Completed |
| `2026-05-19-code-duplication-sweep-plan.md` | 91 | 146 | 62.3% | In-Flight (55 steps open) |
| `2026-05-19-iva-compensation-chain-plan.md` | 7 | 9 | 77.8% | In-Flight (2 steps open) |
| `2026-05-19-live-iva-compensation-wallet-plan.md` | 14 | 17 | 82.4% | In-Flight (3 steps open) |
| `2026-05-19-modelo-130-relation-regression-plan.md` | 0 | 9 | 0.0% | In-Flight (9 steps open) |
| `2026-05-19-profile-lifecycle-disaster-plan.md` | 10 | 47 | 21.3% | In-Flight (37 steps open) |
| `2026-05-19-schema-hardening-plan.md` | 15 | 15 | 100.0% | Completed |
| `2026-05-20-schema-hardening-plan.md` | 101 | 101 | 100.0% | Completed |
| `2026-05-13-google-oauth-plan.md` | 0 | 183 | 0.0% | Backlogged (183 steps open) |
| `2026-05-14-ledger-transaction-lifecycle-plan.md` | 0 | 10 | 0.0% | Backlogged (10 steps open) |
| `2026-05-14-secure-backend-passkey-bucket-plan.md` | 0 | 52 | 0.0% | Backlogged (52 steps open) |
| `2026-05-14-settings-di-plan.md` | 1 | 19 | 5.3% | Backlogged (18 steps open) |

### 3. Remaining Unchecked Steps: Epic Master Plan
The 51 unchecked steps remaining in the core `2026-05-13-cli-workflow-redesign-epic-plan.md` are detailed below:

#### Wave 28: Currency Normalization and Decoupling (10 open steps)
- `W28.P139.S0830` - Add persistence or registry integration tests for currency normalization layer; `tests/domain/currency`.
- `W28.P139.S0831` - Add negative tests proving rejected aliases do not reach currency normalization layer; `tests/entrypoints/cli`.
- `W28.P139.S0832` - Add command behavior tests that exercise currency normalization layer through real services; `tests/entrypoints/cli`.
- `W28.P139.S0833` - Add end-to-end workflow coverage for currency normalization layer; `tests`.
- `W28.P140.S0835` - Expose accepted command handlers for currency normalization layer under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- `W28.P140.S0836` - Keep argument parsing for currency normalization layer separate from backend behavior; `src/aeat/entrypoints/cli`.
- `W28.P140.S0837` - Delegate currency normalization layer execution to centralized backend services; `src/aeat/entrypoints/cli`.
- `W28.P140.S0838` - Render currency normalization layer results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- `W28.P140.S0839` - Handle currency normalization layer failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- `W28.P140.S0840` - Validate help text for currency normalization layer uses accepted vocabulary only; `tests/entrypoints/cli`.

#### Wave 57: Evidence Bundle Lifecycle Auditing (11 open steps)
- `W57.P282.S1687` - Audit duplicate implementations that overlap evidence bundle lifecycle; `src/aeat/application/evidence`.
- `W57.P282.S1688` - Delete duplicate backend branches that compete with evidence bundle lifecycle; `src/aeat/application/evidence`.
- `W57.P282.S1689` - Remove stale aliases that bypass the canonical service for evidence bundle lifecycle; `src/aeat/entrypoints/cli`.
- `W57.P282.S1690` - Migrate internal callers to the canonical service for evidence bundle lifecycle; `src/aeat/application/evidence`.
- `W57.P282.S1691` - Remove stale fixtures and tests that encode duplicate behavior for evidence bundle lifecycle; `tests/application/evidence`.
- `W57.P282.S1692` - Update boundary inventory entries that describe duplicate behavior for evidence bundle lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.
- `W57.P284.S1701` - Add negative tests proving rejected aliases do not reach evidence bundle lifecycle; `tests/entrypoints/cli`.
- `W57.P284.S1702` - Add command behavior tests that exercise evidence bundle lifecycle through real services; `tests/entrypoints/cli`.
- `W57.P284.S1703` - Add end-to-end workflow coverage for evidence bundle lifecycle; `tests`.
- `W57.P284.S1704` - Run the targeted test slice for evidence bundle lifecycle without skips or xfails; `tests/application/evidence`.
- `W57.P285.S1710` - Validate help text for evidence bundle lifecycle uses accepted vocabulary only; `tests/entrypoints/cli`.

#### Wave 63/68/72: Declarations, Exports, and Ratios (8 open steps)
- `W63.P311.S1853` - Expose declaration verification through `aeat app modelo verify` and `aeat app modelo reconcile` only; `src/aeat/entrypoints/cli/_modelo.py`.
- `W68.P326.S1913` - Expose exports only through `aeat app modelo export` and `aeat app ledger export`; `src/aeat/entrypoints/cli`.
- `W72.P347.S2014` - Ship link, check, preflight verbs in `aeat app ledger` wired to existing backend services; `src/aeat/entrypoints/cli`.
- `W72.P347.S2015` - Ship reconcile and history verbs in `aeat app modelo` wired to existing application services; `src/aeat/entrypoints/cli`.
- `W72.P348.S2019` - Add CLI surface tests for link, check, preflight, reconcile, history exercising real backend services; `tests/entrypoints/cli`.
- `W72.P348.S2022` - Add a regression test asserting the reconciled `aeat app ledger` verb count matches the Wave 71 canonical spine plus ratified axes; `tests/entrypoints/cli`.
- `W72.P349.S2024` - Validate `aeat app modelo help` and `aeat app ledger help` enumerate canonical CRUD plus ratified axes; `src/aeat/entrypoints/cli`.

#### Wave 74: Profile Management Rebuilding (3 open steps)
- `W74.P355.S2058` - Implement duplicate, export, import, validate, preflight per the `config-cli-profile-surface` ADR; `src/aeat/application/profile`.
- `W74.P357.S2067` - Wire bucket events for every mutating verb (`profile.created`, `profile.removed`, `profile.updated`, `profile.duplicated`, `profile.exported`, `profile.imported`, `profile.activated`); `src/aeat/domain/buckets`.
- `W74.P358.S2069` - Add service-contract tests for `ProfileLifecycleService` covering all CRUD verbs plus use, duplicate, export, import, validate, preflight; `tests/application/profile`.
- `W74.P359.S2074` - Register the full profile verb tree under `aeat config profile` and render every command via `_emit`; `src/aeat/entrypoints/cli/_config`.

#### Wave 77: Bucket Maintenance and Ratios (10 open steps)
- `W77.P370.S2131` - Implement `BucketMaintenanceService` with verbs browse, search, export, import, rename, delete documented as lifecycle operations; `src/aeat/application`.
- `W77.P370.S2132` - Add Pydantic command and result contracts and ensure destructive operations require explicit yes flag; `src/aeat/application`.
- `W77.P370.S2133` - Add `bucket.exported`, `bucket.imported`, `bucket.renamed`, `bucket.deleted` enum members; `src/aeat/domain/buckets`.
- `W77.P372.S2140` - Wire `ledger.ratios.set` and `ledger.ratios.unset` event emission per ADR; `src/aeat/application/ledger`.
- `W77.P373.S2145` - Add service-contract tests for `BucketMaintenanceService`; `tests/application`.
- `W77.P373.S2146` - Add CLI surface tests for `aeat app ledger ratios` and `aeat config bucket maintenance` verbs; `tests/entrypoints/cli`.
- `W77.P373.S2147` - Add destructive-action safeguard tests asserting delete refuses without explicit yes; `tests/entrypoints/cli`.
- `W77.P373.S2148` - Run the Wave 71 contract-conformance harness with key-value-exception and lifecycle-state-verb annotations; `tests/entrypoints/cli`.
- `W77.P374.S2150` - Register browse, search, export, import, rename, delete verbs under `bucket_app`; `src/aeat/entrypoints/cli/_config`.
- `W77.P374.S2152` - Update apex ADR section 3.4 and 4.2 to document the dual annotation and mark R08 closed by Wave 77; `.vault/adr`.
- `W77.P374.S2153` - Amend `app-ledger-ratios-shape` and bucket child ADRs; `.vault/adr`.

#### Wave 81: Agenda and Overview Decoupling (5 open steps)
- `W81.P390.S2232` - Add `next_due` field to agenda payload per apex section 4.1; `src/aeat/application/overview`.
- `W81.P390.S2233` - Implement backlog and explain verbs per the adjudication; `src/aeat/application/overview`.
- `W81.P393.S2247` - Add CLI surface tests for every overview verb per the adjudicated grammar; `tests/entrypoints/cli`.
- `W81.P393.S2248` - Add negative tests asserting `aeat deadlines` verbs are unknown; `tests/entrypoints/cli`.
- `W81.P394.S2249` - Register the reconciled overview verb tree; `src/aeat/entrypoints/cli`.

#### Wave 83/85: Application Setup and Reconciliation (3 open steps)
- `W83.P400.S2281` - Wire emission of `bucket.created`, `profile.created`, `profile.activated`, `profile.updated`, `auth.provider.configured`, optional `config.env.updated`, `setup.state.migrated` events; `src/aeat/application/setup`.
- `W85.P412.S2342` - Wire `aeat app modelo reconcile from-justificante PATH` CLI verb to existing reconciler closing Wave 64; `src/aeat/entrypoints/cli/_modelo.py`.
- `W85.P414.S2349` - Register Modelo 036 lifecycle verbs (alta, modificacion, baja) under `aeat app modelo` and render via `_emit`; `src/aeat/entrypoints/cli/_modelo.py`.

### 4. Critical Dependencies and Subsidiary Plans
Several specific active tracks support the closure of the Master Plan:
- **Disaster Recovery Strategy (`2026-05-19-profile-lifecycle-disaster-plan.md`)**: Currently at 21.3% completion. This plan directly governs the recovery logic and atomicity of profile storage writes, containing 37 open steps mapping the stabilization of `SecureObjectRepository`, atomic profile initialization, setting database URLs, and newcomer retests.
- **IVA Compensation Wallet & Chain (`2026-05-19-iva-compensation-chain-plan.md` and `2026-05-19-live-iva-compensation-wallet-plan.md`)**: High completion status (77.8% and 82.4% respectively). These address the critical carrying-forward rules for VAT. Only 5 open steps remain combined, ensuring that the live AEAT wallet integration and local recurrence logic are appropriately isolated.
- **Modelo 130 carrying-forward regressions (`2026-05-19-modelo-130-relation-regression-plan.md`)**: Currently at 0% completion with 9 open steps. It addresses the restoration of same-year negative-result carry-forwards under Article 110 of RD 439/2007, resolving recent loader regressions.

## Recommendations

1. **Prioritize the Modelo 130 and IVA Compensation Tracks**: Execute the remaining steps in the IVA Compensation Chain and Modelo 130 Relation Regression plans to lock down tax-carrying correctness before pursuing UI/UX-focused CLI decodes.
2. **Execute the Profile Lifecycle Disaster Recovery Plan**: Resolve the 37 outstanding steps in `2026-05-19-profile-lifecycle-disaster-plan.md`. This is a critical structural blocker ensuring profile and bucket safety.
3. **Execute the remaining Wave 28 and Wave 57 Steps**: Decouple the currency normalization and evidence bundle lifecycles to clear technical duplication paths and ensure a clean entrypoint structure.
4. **Adhere to the Dual-Subagent Documentation Workflow**: Use the designated Researcher/Author/Editor workflow for any subsequent updates to project document repositories.

