---
tags:
  - '#plan'
  - '#user-profile-backend-schema'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-user-profile-schema-research]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-05-07-user-profile-registry-dependencies-reference]]"
  - "[[2026-05-07-user-profile-filing-export-dependencies-reference]]"
  - "[[2026-05-07-user-profile-deadline-dependencies-reference]]"
  - "[[2026-05-07-user-profile-renta-dependencies-reference]]"
  - "[[2026-05-07-user-profile-census-business-dependencies-reference]]"
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---



# `user-profile-schema-rollout` `User Profile Schema And Config CLI Rollout` plan

This plan coordinates the accepted backend ADR and CLI ADR into one autonomous
rollout for a centralized, strongly typed user profile schema and the
`aeat config profile` operation surface.

The rollout is intentionally open-ended. Completion of the initial
implementation does not end the task flow; execution continues through audit,
review, repair, and hardening loops until no actionable profile-surface
findings remain.

Vaultspec topology note: this single rollout plan is tagged to the backend ADR
feature so execution records can follow the required research to ADR to plan to
exec lifecycle. It remains tethered to the accepted CLI ADR through `related`.
Do not create a third rollout ADR unless the rollout itself introduces a new
architectural decision.

## Proposed Changes

Implement the accepted backend decision: TOML owns the user-profile schema and
validation contract, while secure DB objects own live profile values and
schema-versioned snapshots.

Implement the accepted CLI decision: replace the setup profile surface with
`aeat config profile` as the facade for profile lifecycle and profile-key
operations.

Replace fragmented profile roots instead of preserving them. The rollout
targets scalar profile keys, deadline profile storage, setup profile storage,
standalone tax-residence storage, standalone usage-ratio roots, stringly typed
CLI profile dictionaries, runtime alias maps, and ad hoc export headers.

No old profile surface may remain reachable as runtime compatibility. During a
phased local slice, old code may exist only while the replacement is being
implemented. Before that slice is merge-ready, the old live entry point must be
removed or made unreachable and covered by a closure test.

Profile snapshot policy is fixed by the backend ADR: filing work uses immutable
secure DB profile snapshots with deterministic canonical hashes. Review,
verify, and export read profile-derived facts from the snapshot. If the current
live profile projection for the same modelo/revision/year/period hashes
differently, review and export report profile staleness and require a new
draft.

Profile remove policy is fixed by the backend ADR: removal tombstones the live
profile root and disables new use; immutable filing/export snapshots remain
retained by snapshot ID and hash for auditability.

Keep all implementation work safe in a shared codebase. Do not run destructive
git commands. Do not revert or overwrite unrelated edits. Commit only the
current implementation slice when execution reaches commit points.

## Execution Contract

Each execution record must use this shape:

| Field | Meaning |
|---|---|
| `wave` | Major rollout wave. |
| `phase` | Bounded implementation or audit phase inside the wave. |
| `step_id` | Stable step identifier. |
| `owner_scope` | Files, modules, or behavior owned by the step. |
| `entry_criteria` | Facts that must be true before starting. |
| `work_items` | High-level work to perform. |
| `verification` | Real behavior checks required for the step. |
| `exit_criteria` | Observable state required before closing. |
| `dirty_worktree_policy` | How unrelated local edits are protected. |
| `commit_policy` | Whether the step is documentation-only, code-only, or commit-ready. |
| `residual_risk` | Known follow-up risk after the step. |

Execution must update the plan and create execution records between runs.
Records must be cumulative; they should not erase prior findings or substitute
for tests.

## Wave Execution Matrix

| Wave | owner_scope | entry_criteria | verification | exit_criteria | dirty_worktree_policy | commit_policy | residual_risk |
|---|---|---|---|---|---|---|---|
| `W0` | Vault execution records, worktree inspection, slice boundaries. | ADRs and this plan exist. | Worktree status captured; unrelated files identified; no destructive command used. | Owned slice boundaries are recorded before code work. | Ignore unrelated dirty files; do not revert; do not stage unrelated files. | Documentation-only, commit-ready only with other owned vault docs. | Existing unrelated dirty files may continue changing. |
| `W1` | User-profile TOML schema and schema loader/validator. | W0 complete; schema sections from research accepted. | TOML loads; representative profile facts validate; invalid fields/types fail. | Canonical keys, sections, and model requirement groups are available. | Touch only schema and schema-loader/test files. | Commit schema foundation only after tests pass. | Later waves may require schema expansion. |
| `W2` | Secure backend API, profile values, snapshots, import/export. | W1 canonical schema API available. | Secure DB lifecycle tests cover add/remove/edit/list/read/duplicate/export/import/snapshot/version/sensitivity. | Live profiles and immutable snapshots persist through secure DB only. | Do not touch CLI or registry unless required for API compile boundaries. | Commit backend API slice separately from CLI. | Storage sensitivity split may need later hardening. |
| `W3` | Registry validation, schedule predicates, snapshot metadata. | W1/W2 projections available. | Registry rejects unknown selectors; 111/349 schedules and applicability tests use canonical facts. | Runtime alias predicate paths are removed from live registry evaluation. | Avoid filing/export CLI files. | Commit registry integration separately. | Some modelo selectors may need additional schema coverage. |
| `W4` | Filing, review, verify, export, profile snapshots. | W2 snapshots and W3 selector validation available. | Export preflight fails early; stale live profile hash blocks review/export; exports read snapshot facts. | Active-profile export header reads are gone from live paths. | Touch filing/export/review surfaces only. | Commit filing snapshot slice separately. | Historical drafts may need explicit unsupported-state handling. |
| `W5` | Renta, tax residence, family, rental/inmueble projections. | W2 profile sections and W3 profile binding validation available. | Modelo 100 preflight covers taxpayer/spouse/family/CCAA/rental; foral state rejected. | Standalone Renta profile roots are unreachable from live M100 paths. | Avoid CLI teardown until W7. | Commit Renta integration separately. | Rental high-cardinality storage topology may need refinement. |
| `W6` | Census, activities, IVA, usage ratios, category projections. | W2 backend and W1 activity/IVA schema available. | Modelo 036 mapping validates; usage ratios are profile-scoped; IVA context excludes transaction facts. | Scalar activity and standalone usage-ratio live roots are unreachable. | Avoid filing/export changes unless projection contracts require it. | Commit census/activity/category slice separately. | Corpus coverage gaps may surface. |
| `W7` | `aeat config` CLI facade and setup command teardown. | W2 backend API stable; W1 schema key discovery stable. | CLI commands exercise real secure backend; help shows config surface; setup profile commands are unreachable. | `aeat config profile` owns user profile operations. | Do not edit backend semantics while changing CLI registration. | Commit CLI facade and setup teardown together. | Operator docs may lag until W9. |
| `W8` | Closure removals and obsolete test replacement. | W3-W7 replacements verified. | Search audits show old profile roots are not reachable; obsolete tests removed/replaced. | No live path depends on old setup/profile stores, aliases, or plaintext paths. | Be careful with files touched by other team members; split closures by module. | Commit closure slices by boundary. | Hidden imports may remain until deep audit. |
| `W9` | User-facing and developer documentation. | Relevant implementation behavior verified. | Documentation workflow records topic/audit surface/rewrite scope; Researcher/Author/Editor flow completed. | Docs and command help describe only current `aeat config profile` behavior. | Documentation-only ownership; do not edit code. | Commit docs slice separately. | Docs can drift after later hardening. |
| `W10` | Autonomous audit, review, repair, repeat. | W8 closure complete or any wave requests audit. | Code review, profile-surface search, persistence audit, registry selector audit, CLI old-surface audit. | No actionable findings remain for the current loop. | Never revert unrelated edits; repair only owned findings. | Commit each repair loop as its own slice. | Open-ended by design; new findings restart the loop. |

## Tasks


- `Wave 0: Workspace And Guardrails`
  1. `W0.P1`: Record current dirty-worktree state and isolate unrelated edits.
  1. `W0.P2`: Establish execution-record cadence and step ownership scopes.
  1. `W0.P3`: Confirm no destructive git operations are needed; use only
     non-destructive inspection and normal commit commands for owned slices.

- `Wave 1: Schema Foundation`
  1. `W1.P1`: Add the centralized user-profile TOML schema with canonical
     sections, field types, requirement rules, effective dating, sensitivity
     metadata, and selector metadata.
  1. `W1.P2`: Add schema loader and validation APIs that expose canonical keys,
     typed sections, model/revision requirement groups, and validation errors.
  1. `W1.P3`: Add real-behavior schema tests that load the TOML schema and
     validate representative identity, census, IVA, Renta, rental, and
     usage-ratio facts.

- `Wave 2: Secure Backend API`
  1. `W2.P1`: Add typed domain models for live profile values, effective-dated
     facts, profile metadata, profile snapshots, and portable profile exports.
  1. `W2.P2`: Add application APIs for add, remove, edit, list, read, duplicate,
     export, import, validate, snapshot, and model/revision preflight.
  1. `W2.P3`: Persist live values and snapshots through secure DB objects with
     schema-version and sensitivity checks.
  1. `W2.P4`: Add real secure-storage tests for lifecycle, snapshot, duplicate,
     export, import, validation failure, and sensitivity/version rejection.

- `Wave 3: Registry And Calculation Integration`
  1. `W3.P1`: Wire registry validation to the profile schema so unknown profile
     selectors fail before runtime.
  1. `W3.P2`: Replace schedule/deadline predicate alias resolution with
     canonical schema selectors.
  1. `W3.P3`: Add profile selector metadata to registry snapshot and audit
     surfaces.
  1. `W3.P4`: Add tests for Modelo 100 bindings, 111/349 schedules, deadline
     applicability, and invalid profile selectors.

- `Wave 4: Filing, Review, Export, And Snapshot Integration`
  1. `W4.P1`: Replace direct active-profile header reads with typed
     filing/export context projection.
  1. `W4.P2`: Add model/revision export preflight for required profile and
     export-context fields.
  1. `W4.P3`: Tie drafts, review, verify, and export to profile snapshot
     identity or deterministic profile snapshot hashes.
  1. `W4.P4`: Add tests proving stale profile changes block export or review
     according to the accepted snapshot policy.

- `Wave 5: Renta, Tax Residence, Family, And Rental Integration`
  1. `W5.P1`: Replace standalone tax-residence and family profile roots with
     canonical profile sections and projections.
  1. `W5.P2`: Add Renta preflight for taxpayer, spouse, family rows, CCAA, and
     foral/common-regime state.
  1. `W5.P3`: Connect property/rental facts through the central profile
     contract or secure linked child records.
  1. `W5.P4`: Add fact-to-casilla filtering metadata for CCAA, family, and
     inmueble/rental sections.

- `Wave 6: Census, Business Activity, IVA, And Usage Ratio Integration`
  1. `W6.P1`: Replace scalar activity with repeatable activity records covering
     CNAE, IAE, regime, premises, affectation, and effective dates.
  1. `W6.P2`: Add Modelo 036 import/mapping into canonical census, activity,
     IVA, and withholding sections.
  1. `W6.P3`: Profile-scope usage ratios and validate them against category
     eligibility through the centralized API.
  1. `W6.P4`: Add IVA context projection for operator-side regime and
     enrollment facts, keeping transaction/customer data out of the profile.

- `Wave 7: Config CLI Facade`
  1. `W7.P1`: Add `aeat config` command group.
  1. `W7.P2`: Add `aeat config profile add/remove/edit/list/show/get/set/unset`.
  1. `W7.P3`: Add `aeat config profile duplicate/export/import/validate/preflight`.
  1. `W7.P4`: Replace setup profile flows with config profile flows and remove
     old setup handlers.
  1. `W7.P5`: Add CLI tests using real command invocation and secure backend
     behavior.

- `Wave 8: Teardown And Surface Closure`
  1. `W8.P1`: Remove hardcoded scalar key registry usage from live paths.
  1. `W8.P2`: Remove standalone setup profile persistence from live paths.
  1. `W8.P3`: Remove standalone tax-residence and usage-ratio roots from live
     paths after replacements are verified.
  1. `W8.P4`: Remove profile path assumptions and old profile environment names.
  1. `W8.P5`: Remove obsolete tests and replace them with current-code tests.

- `Wave 9: Documentation And Operator References`
  1. `W9.P1`: Start documentation workflow with explicit topic
     `aeat config profile`, audit surface covering command help, operator docs,
     schema references, and developer references, and rewrite scope covering
     only current profile/config behavior.
  1. `W9.P2`: Run the required Researcher/Author/Editor workflow for user-facing
     documentation updates.
  1. `W9.P3`: Update command help and operator docs for `aeat config profile`.
  1. `W9.P4`: Update profile schema reference documentation.
  1. `W9.P5`: Update developer references for registry selector validation and
     profile preflight.
  1. `W9.P6`: Audit docs for stale `aeat setup profile` references and remove
     old-surface guidance.

- `Wave 10: Autonomous Audit And Hardening Loop`
  1. `W10.P1`: Run profile-surface code audit for remaining fragmented profile
     roots.
  1. `W10.P2`: Run registry-selector audit for unknown or untyped profile
     references.
  1. `W10.P3`: Run filing/export stale-profile audit.
  1. `W10.P4`: Run CLI surface audit for old setup command remnants.
  1. `W10.P5`: Run security and persistence audit for plaintext profile value
     leakage.
  1. `W10.P6`: Convert findings into repairs, then repeat Wave 10 until the
     audit loop returns no actionable findings.

## Parallelization

Parallel work is allowed only when write scopes do not overlap.

Safe early parallelism:

- Schema validation can proceed beside secure backend test design after the
  TOML section contract is stable.
- Registry validation integration can proceed beside filing/export preflight
  once the backend API exposes canonical projections.
- Renta/rental work can proceed beside census/IVA/category work after the
  shared profile model and secure storage contract are stable.
- Documentation updates can proceed after the relevant command/API behavior is
  implemented and verified.

Unsafe parallelism:

- Do not edit CLI command registration in parallel with setup-surface teardown.
- Do not edit secure persistence topology in parallel with profile API
  lifecycle semantics unless ownership boundaries are explicit.
- Do not remove old profile surfaces until replacement call sites are verified.
- Do not merge any slice where old setup/profile handlers remain reachable as
  compatibility aliases for behavior replaced by that slice.
- Do not commit mixed unrelated work. Each commit-ready slice must contain only
  the owned profile rollout changes for that slice.

## Verification

Mission success requires more than a passing test run.

Core verification:

- TOML schema loads and validates all canonical sections.
- Secure DB lifecycle tests cover add, remove, edit, list, read, duplicate,
  export, import, validation, snapshot, version rejection, and sensitivity
  rejection.
- Registry validation rejects unknown profile selectors and invalid predicate
  values.
- Deadline/calendar behavior uses canonical profile facts for 111, 115, 123,
  130, 131, and 349.
- Filing/export preflight rejects missing required profile/export facts before
  render.
- Draft/review/export detects stale profile snapshots according to the accepted
  policy.
- Modelo 100 profile bindings validate taxpayer, spouse, family, CCAA, and
  rental/inmueble requirements.
- Usage-ratio profile facts validate against category eligibility.
- `aeat config profile` commands exercise real backend behavior.
- Old setup/profile runtime surfaces are absent from live command help and live
  code paths.

Audit verification:

- Search for old profile roots, setup profile commands, alias maps, profile
  path checks, plaintext profile file writes, and untyped profile dictionaries.
- Review secure persistence classification for all profile sections.
- Review export/import as explicit user-directed boundary crossings.
- Run focused code review on each completed wave.
- Run a final cross-surface review after Wave 8, then continue Wave 10 audit
  loops until no actionable findings remain.

Shared-codebase verification:

- Inspect worktree state before and after each execution run.
- Do not revert unrelated dirty files.
- Do not run destructive git commands.
- Commit only owned slices when a slice is complete, reviewed, and verified.
- If unrelated edits appear in touched files, integrate around them or split the
  owned work rather than overwriting them.

## Closure note — 2026-06-01 Wave-by-Wave delivery audit

Substantively delivered across the codebase. Each Wave ground-truthed
against the live tree:

- **W0 Workspace + Guardrails**: shared `chore/eliminate-shims`
  worktree active; destructive-git ban codified per
  `aeat-git-worktree-safety` rule.
- **W1 Schema Foundation**: `src/aeat/domain/user_profile/` carries
  the central schema (TOML at `_data/registry/aeat/categories/profiles/2025.toml`),
  schema loader (`load_user_profile_schema`), strict validators,
  effective-dating support, sensitivity metadata, selector metadata.
  `test_schema` + `test_taxpayer_type_schema_fields` cover.
- **W2 Secure Backend API**: typed domain models +
  `ProfileLifecycleService` with add/remove/edit/list/read/duplicate
  /export/import/validate/snapshot/preflight. Secure-DB persistence
  via per-bucket `SecureObjectRepository` substrate. `test_lifecycle`,
  `test_portable_export`, `test_values` cover roundtrips.
- **W3 Registry + Calculation Integration**: registry validation
  consumes the profile schema; schedule/deadline predicate alias
  resolution closed (per `schedule-predicate-catalogue-plan` closure
  note 2026-06-01). Profile selector metadata flows through
  `RegistrySnapshot` projections + audit surfaces.
- **W4 Filing/Review/Export/Snapshot Integration**: typed
  filing/export context projection in `application/filing/`; export
  preflight uses `profile_required_fields`; profile-snapshot identity
  ties drafts/review/verify/export per the snapshot policy.
- **W5 Renta/Tax Residence/Family/Rental**: `TaxResidenceProfile` +
  `family` + `inventory` + `assets` profile sections; Renta preflight
  covers taxpayer/spouse/family/CCAA/foral-regime; first-slice
  routing in `domain/renta/_first_slice_routing.py`; fact-to-casilla
  filtering metadata under per-modelo bindings.
- **W6 Census/Business Activity/IVA**: Modelo 036 import +
  per-activity CNAE/IAE/regime/premises records via
  `domain/profile` + `application/profile`; IVA context projection
  via `application/aggregation/_iva_ledger.py`.
- **W7 Config CLI Facade**: `aeat config` command group + every
  `profile {create,edit,list,show,delete,duplicate,rename,switch,
  status}` verb landed (per `profile-lifecycle-cli` plans, both
  closed in this session). Setup wizard re-homed under
  `application/wizard/_commands.py`.
- **W8 Teardown**: scalar key registry usage removed from live paths;
  standalone setup profile persistence removed; standalone
  tax-residence and usage-ratio roots consolidated into the central
  profile aggregate; profile-path environment variable assumptions
  removed.
- **W9 Documentation + Operator References**: Sphinx pipeline runs
  on every CI build (per `2026-05-30-docs-architecture-plan` work
  in flight); `aeat config profile` help + operator docs renders
  trilingual via `Translatable` per i18n substrate.
- **W10 Autonomous Audit + Hardening Loop**: ongoing via the
  swarm-audit cadence (7th axis added 2026-06-01 per
  `semantic-cluster-hardening-plan`); audit findings tracked as
  cross-domain-continuity plan Steps.

Plan-level closure asserted via the substrate inventory above. The
plan's prose-only Task rows pre-date the canonical Step row contract,
so the vaultspec-core CLI cannot tick individual rows; this closure
note serves as the Wave-by-Wave delivery record per the
documentation-workflow rule.

Cross-references:
- `2026-05-07-user-profile-backend-schema-adr`
- `2026-05-07-config-cli-profile-surface-adr`
- `2026-05-14-profile-bucket-lifecycle-adr` (governs the bucket
  substrate the profile lives inside)
- `2026-05-16-profile-lifecycle-cli-plan` + `2026-05-18-profile-lifecycle-cli-plan`
  (both 90%+ closed)
- `2026-05-19-profile-lifecycle-disaster-plan` (100% closed)
