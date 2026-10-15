---
tags:
  - '#plan'
  - '#startup-service-repair'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-13-native-agent-adr]]'
  - '[[2026-10-13-package-verification-adr]]'
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:55e7a73805e8aa3c733c1d52de5f7020731d9c279bef05b2405d0a756576ebaa'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries governing ADRs, if any.
       Steps inherit their evidence transitively. Direct supporting
       evidence links are optional; per-row footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace startup-service-repair with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries governing ADRs; Steps inherit their evidence transitively.
     Direct supporting evidence links are optional. A decision-free plan
     records its coverage assessment in the Description.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution artifact: the plan's ledger.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 until `vaultspec-core vault check all --fix` adds it).
     The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Select the smallest hierarchy that clarifies coordination:
       L1 = a flat sequence of cohesive revisions, including broad changes.
       L2 = Phases clarify groups of Steps.
       L3 = Waves clarify dependencies between groups of Phases.
       L4 = an Epic coordinates a program with external tracking.
     Duration, file count, package count, or short parallel work alone
     never requires a higher tier.
     Between two tiers take the smaller and promote later.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- COHESIVE GRANULARITY:
     One Step is one cohesive, verifiable commit. Coordinated repeated edits
     may share a row when scope and verification are explicit. Separate
     unrelated outcomes. Name the bounded files or area, expected creations,
     and intended result; avoid unspecified catch-all work. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change; the `plan_edit` and `plan_progress`
     MCP tools reach the Step verbs only, and the above-Step verbs run
     through the CLI. Hand edits are forbidden and
     flagged by `vaultspec-core vault plan check`; canonical-identifier
     preservation is guaranteed only when a verb performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `startup-service-repair` plan

<!-- One-line headline summary plan. -->

## Description

Approved 2026-10-14. The user explicitly requested fixes for all diagnosed startup failures, slow process management, and actionable service error reporting. Repairs preserve accepted canonical environment and desktop shell ownership; no new authority, persistence scheme, or agent source dependency is introduced. Existing concurrent edits are preserved.

Continued authorization on 2026-10-15 requires actual non-GUI Python service, runtime and agent behavior, with separate native provider login per profile; Claude is selected. S07 repairs omission of the agent's already-declared Node/ACP runtime dependency closure. This Cadrumo integration uses the later accepted native-agent CMake/private-wheel topology, including shared application custom site-packages and colocated non-Python assets. The earlier agent record's separate complete interpreter/install and sibling placement are superseded only for this integration; that record remains unchanged for standalone agent shipping. Its pinned runtime dependency and user-only provider CLI constraints remain respected. Package-verification governs the unmodified built-package acceptance boundary and canonical-environment-application-internals governs image profiles. No new install topology or hosted proof bypass is introduced.

S08 was explicitly approved on 2026-10-15 when the user answered "Approve the proposed repair" for the external `Y:/code/cadrumo-agent-worktrees/main/.vault/adr/2026-10-15-cadrumo-integration-hosted-certification-bootstrap-adr.md`. It permits an ordinary-turn-proven, otherwise-admitted lane to use the normal hosted route while hosted-package certification is disclosed as pending in catalog, service status and frozen selection. This is a scoped change to the certification startup rule, not evidence that a hosted turn has passed. Credentials, installed-version checks, runtime authority, hosted layout and per-run permissions remain enforced. Only an actual completed package-backed hosted turn may earn the hosted proof record.

<!-- First line after approval: `Approved yyyy-mm-dd`, written by the
orchestrator after establishing scoped authorization, including an explicit
advance authorization. Record its basis; ask only when it is absent. Then briefly describe the proposed work.
Reference `{adr}`s, `{research}`, `{reference}`. Supporting documentation
must be read when relevant. State the decision coverage assessment; when no
costly decision is involved and no ADR governs, say so. With several ADRs,
map their scope to Steps at L1 or the relevant containers at higher tiers. -->

## Steps

- [ ] `S01` - Preserve actionable agent CLI and native startup errors and invocation timing; `src/cadrumo_agent_service/main.py, src/cadrumo_agent_service/service.py, src/cadrumo_agent_service/host/store_lifecycle.py, src/cadrumo_agent_service/host/tests/test_service_failure.py, native/application/src/diagnostics/service.rs, native/desktop frontend records and agent retry surfaces, owning tests`.
- [ ] `S02` - Coalesce sign-in observations and make agent retry supervision responsive and bounded; `native/desktop/src-tauri/src/shell/sign_in, native/desktop/src-tauri/src/agent/supervisor.rs`.
- [ ] `S03` - Verify corrected launch environment and service diagnostics in the rebuilt Windows package; `native/tests/environment_launch_probe.py, dev/runtime_lifecycle/agent_live.py, build/windows-x64, direct non-GUI service/runtime/provider-home and live-provider validation`.
- [ ] `S04` - Diagnose and repair profile worker deadline cascades and distinguish ordinary client closes from refusals; `src/cadrumo/adapters/local_runtime/profile_worker_transport.py, src/cadrumo/adapters/local_runtime/server_connection_handling.py, src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py, owning tests`.
- [ ] `S05` - Preserve the declared external CLI binary directories across service, gateway and worker launches; `native/application-environment.toml, native/CONTRACT.md, native/platform/src/launch.rs, src/cadrumo_agent_service/host/launch_environment.py and tests, dev/packaging/native/environment_conformance.py and tests, packaged CLI resolution verification`.
- [ ] `S06` - Enable explicit provider-native sign-in in the isolated profile home through the agent-owned operator command; `src/cadrumo_agent_service/admin.py and service.py, adapters/agent_provider_catalog.py and sign-in capability/preparation tests, native/application-environment.toml and native/platform/src/launch.rs and native/CONTRACT.md, dev/packaging/native/application_environment.py and owning checks, cadrumo-agent CLI operator auth command and tests`.
- [ ] `S07` - Package the agent-declared pinned Node and Claude ACP runtime closure without any provider CLI and verify real packaged Claude startup; `create dev/packaging/native/agent_runtime.py and owning tests, native/agent/runtime.json, native/cmake/Agent.cmake and Packaging.cmake, dev/packaging/native/cmake_build.py and assemble.py and update_agent.py and owning package checks, src/cadrumo_agent_service/service.py and host/launch_environment.py and tests, native/tests/agent_smoke.py and its documented pyproject.toml subprocess grant, native/CONTRACT.md`.
- [ ] `S08` - Implement the user-approved hosted certification startup amendment while retaining ordinary proof and all runtime, sign-in and permission controls; disclose pending certification and earn the actual packaged hosted proof; `cadrumo-agent providers/lane_admission.py, API startup and catalog schemas, frozen run selection and tests, src/cadrumo_agent_service/adapters/provider_catalog_metadata.py and owning service contract tests, packaged direct service/model/tool verification`.

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- Progress is recorded through the plan verbs (`plan_progress`,
     `vaultspec-core vault plan step check`), one Step at a time. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     For user-requested coordination across the program and its tracker,
     vaultspec-projectmanager owns that context and assignments; this
     plan remains the home of implementation sequencing.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

S01 (root, Python diagnostics) and S02 (desktop worker, Rust sign-in and supervisor) may execute concurrently with disjoint ownership. S04 (runtime worker transport) may run concurrently with S01 and S02, with disjoint transport ownership. S03 follows all repairs; root owns package rebuilds, shared gates, ledger updates, commits, and final review.

Within S07, the runtime-closure helper and its tests may run independently of service environment composition. The root owns the CMake graph, assembly, shared metadata and package builds. The runtime helper worker owns only the new agent_runtime module, its tests and runtime pin declaration. The service worker owns only launch_environment and its focused tests. Workers preserve concurrent edits; the root integrates and reviews before rebuilding. No native package process proof runs concurrently with a package build.

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

S08 agent admission/catalog/frozen-selection work and Cadrumo service status projection may run concurrently with disjoint ownership. The agent worker owns external production contracts and their tests; the service worker owns service.py, service-owned status DTOs and focused tests. The root owns plan/ledger metadata, integration checks and native builds. Proof-client corrections remain confined to existing source-run qualification paths. No native package proof or interactive login is prepared while another native package build is quiescing the application.

## Verification

Focused Python diagnostics and lifecycle tests, Rust supervisor and observation tests, configured lint and type checks, and the packaged environment launch probe must pass. Verify secrets remain scrubbed, stale sign-in is never authority, retry failures remain visible, and the packaged agent passes stores-state with the actual runtime environment.

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step is closed (`- [x]`) and the final
cohesive review passes. At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

Review follows the vaultspec system section. L1 has no Phase close;
coincident plan-close and handoff gates share one integrated review. -->
