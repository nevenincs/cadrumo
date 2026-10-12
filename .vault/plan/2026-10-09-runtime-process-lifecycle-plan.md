---
tags:
  - '#plan'
  - '#runtime-process-lifecycle'
date: '2026-10-09'
tier: L1
related:
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-06-28-product-packaging-adr]]'
modified: '2026-10-11'
body_schema: body-v2
body_hash: 'sha256:56d1fa73fe18032625013a4de4563d9db22c234b5c48eae225d509341941624c'
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
     Replace runtime-process-lifecycle with a kebab-case feature tag, e.g. #foo-bar.
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

# `runtime-process-lifecycle` plan

<!-- One-line headline summary plan. -->

## Description

Approved 2026-10-09

Basis: the user requests implementation of command-driven pytest lifecycle, authentication, recovery and latency tests with real binaries and native IPC. Accepted manager and supervisor decisions govern test resource ownership and runtime recovery; application sign-in governs native login proof and revocation. No new costly decision is introduced. The shipping manager refuses synthetic roots; the existing debug-only fixture feature supplies a driver of the real admitted supervisor core and real packaged runtime. This evidence does not claim installed-entrypoint, tray, autostart or live AEAT acceptance. Semantic code discovery was unavailable; bounded source inspection was used.


2026-10-09 scope continuation authorized by the operator: verify existing runtime/manager lifecycle, native install/unregister and scope/elevation boundaries; ensure canonical CMake verifies real CLI/TUI/MCP protected access and refusal; expose GUI-observable authentication/profile/runtime state signals. Prefer refinement of established checks and Tauri channel infrastructure over duplicate scripts. Active profile selection is not session or MCP grant authority. Windows SCM services remain excluded; Background Services is the interactive per-user manager. Source inspection found existing manager supervision and native maintenance owners, but no packaged authenticated client matrix in CTest and no GUI sign-in subscription. S02 closes that acceptance coverage gap; S03 adds only public observation, under existing desktop-shell and sign-in authority, without changing authentication or runtime management authority. No installation or login registration will be performed on this host.


The user explicitly authorized removal of native desktop/logon admission on 2026-10-09. S04 removes launch-context rejection rather than treating Session 0, missing desktop witnesses or elevation as test-host limitations. Native same-account IPC peers and real passwords, receipts and exact-profile MCP grants remain required. The governing manager and sign-in ADRs contain the authorized amendment.

Continuation authorized by the operator: ensure packaged CLI, TUI and MCP connect and can perform authenticated work; runtime lifecycle ownership may be initiated by Cadrumo or supplied by the installed runtime-manager surface. Both routes retain the existing manager as supervisor, and external clients remain connect-only. Reuse the current harness and canonical CMake health lane. Worker custody-observation failures must retain their original error without emitting private state. Credential-backed acceptance uses an actual same-account native logon with working OS custody when available; Session 0 startup/password verification remains separate evidence and no admission gate or mock credential store is restored.

Approved 2026-10-10 continuation: the operator authorized implementation hardening following the ranked coverage review. S05-S07 refine the existing real-binary harness for all-client crash recovery, exact manager death/adoption, and unfinished admitted-operation recovery. Accepted manager architecture governs survivor adoption: manager death must not kill its runtime; external clients remain connect-only. Existing operation journal/replay decisions govern S07; start/resume require fresh session authority and settled operation identity is retained. No new protocol, persisted schema, mock credential backend or launch-context gate is introduced. Execute serially and preserve shared edits; reuse existing canonical CMake enrollment. Verification includes actual authenticated responses, same-boot survivor adoption, manager-owned runtime restart after adoption and durable pre-execution operation state. Host installation/logon registration and induced OS shutdown remain outside this isolated test pass.

S07 grounding correction on 2026-10-10: diagnostics.read permits resume; auth.local-read does not. Abrupt owner death retains the production ten-minute operation lease, so immediate continuation correctly refuses. Verify canonical expiry/takeover with fresh authority and one persisted execution phase, without editing storage, shortening leases or advancing clocks. Increase only the existing debug-driver watchdog to 1200 seconds and CTest acceptance timeout to 1800 seconds so the real lease interval can be verified; native/cmake/Packaging.cmake is an additional S07 verification row.

Approved 2026-10-10: the user clarified optional installation, a machine-start installed manager for admin scope, login startup for user scope, GUI fallback using the existing supervision core, and startup that ensures a live supervisor regardless of registration. S11 and S12 implement that authorized architecture amendment. S13 and S09 verify shipping startup, supervisor ownership and authenticated client readiness; no XML-only evidence substitutes for installed execution.

## Steps

- [x] `S01` - Implement command-driven real manager-core and native runtime authentication lifecycle acceptance with isolated ownership and timing evidence; `.importlinter tooling inventory and regenerated dev/quality/metadata/import_load_targets*.json, native/manager debug-only driver, native/cmake/Manager.cmake opt-in targets, dev/runtime_lifecycle harness, tests and command documentation`.
- [x] `S02` - Refine existing lifecycle coverage for packaged CLI, headless TUI and MCP protected access, refusal and profile isolation, and enroll the existing acceptance harness in canonical CMake verification; `dev/runtime_lifecycle, native/cmake/Packaging.cmake, existing native package test helpers and focused native client tests`.
- [x] `S03` - Publish canonical nonsecret sign-in state changes through the existing token-checked Tauri channel pattern, consume them in the shell and document precise GUI signals; `native/desktop/src-tauri/src/shell/sign_in, native/desktop/src-tauri/src/app.rs close integration, native/desktop/frontend/src/ipc/contract.ts and shell host/signIn adapters, existing shell tests and frontend README`.
- [x] `S04` - Remove native desktop/logon admission rejection; `Manager, harness and runtime launch-context gates with native peer and credential authentication preserved and command-only acceptance verified.`.
- [x] `S05` - Verify packaged CLI TUI and MCP recover authenticated protected work after exact runtime crash using existing manager and client harness; `dev/runtime_lifecycle/tests/test_clients.py and existing native client recovery owners if exposed failures require fixes`.
- [x] `S06` - Verify exact manager death leaves its runtime serving and explicit successor adopts without duplicate ownership, then restores supervision; `dev/runtime_lifecycle/harness.py, native/manager/tests/fixture/lifecycle.rs and manager adoption/ownership owners if required`.
- [x] `S07` - Verify unstarted admitted work survives runtime crash and executes once through a fresh authenticated session; `dev/runtime_lifecycle/tests/test_lifecycle.py and existing runtime journal/recovery owners if required`.
- [x] `S08` - Correct complete desktop bundle delivery and verify the shipping startup installation prerequisite; `native/cmake/InstallerFlow.cmake, native/cmake/Packaging.cmake, existing packaging verification owners and tests`.
- [ ] `S09` - Require real shipping desktop provisioning and installed manager dispatch to reach verified runtime readiness in application acceptance; `existing native desktop startup and packaged acceptance owners`.
- [x] `S10` - Quiesce verified running product processes before package replacement and force termination after a bounded graceful shutdown; `existing native build action and packaging process helpers with isolated real-process regression tests`.
- [ ] `S11` - Embed the existing supervisor core in the desktop host with installed-manager arbitration, ongoing takeover, verified packaged startup without installation, and typed watchdog-driven GUI readiness/recovery/failure observations; `native manager host lifecycle and authenticated manager IPC, native desktop manager startup/health/observation commands and tests, frontend account gating and existing manager presentation scenarios, canonical locale strings and precise signal documentation`.
- [ ] `S12` - Implement optional machine-start lifecycle broker and retain per-user login manager installation without changing taxpayer authentication context; `native manager Windows SCM broker, native installer MSI service authoring and service controls, existing build quiescence and real native tests`.
- [ ] `S13` - Rebuild complete CMake package and verify actual desktop-owned and installed-manager supervision paths with failure-producing acceptance; `Canonical CMake package acceptance, existing real CLI TUI MCP harness, selected minimal disposable Windows guest/account and genuine boot/login/upgrade evidence, bounded physical corpus basename repair with coherent manifest/registry/sidecar locators and canonical authority publication, default and actual-prefix UTF16 destination admission before MSI mutation under the product-packaging 2026-10-11 scoped amendment, with failed immutable cohorts and all source bytes preserved.`.

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

S01-S10 execute serially as recorded. At the user's explicit request, S11 GUI fallback and S12 Windows service/installer implementation may execute in parallel with disjoint owners. The GUI owner edits desktop startup and the new embedded host plus manager IPC; the service owner edits the new SCM broker, manager invocation/main and MSI/registration owners. The root owns shared module exports, CMake/build quiescence, acceptance execution and vault records. Builds sharing one CMake/Cargo/staging directory execute serially. S13 follows both implementations.

## Verification

Run native formatting and Clippy, focused pytest and Python lint/format/type checks. The Windows command exercises real native peer verification without desktop/session/elevation admission, authenticated profile reads, old-session refusal, exact-handle runtime termination, manager-owned recovery, durable operation observations and process cleanup. Canonical CMake package verification must run the packaged CLI/TUI/MCP matrix. Review integrated ownership and secret handling before completion. Actual failures are failed acceptance, never passing mocks or skipped tests.
