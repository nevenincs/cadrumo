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
  - '[[2026-10-12-live-agent-evaluation-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-15-native-package-ci-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:0ad26ebe7ecfcac59ff1f3a6d2b535b6aee79b38c2a95dde20dc738e0b60c739'
---

# `startup-service-repair` plan

## Description

Approved 2026-10-14. The user explicitly requested fixes for all diagnosed startup failures, slow process management, and actionable service error reporting. Repairs preserve accepted canonical environment and desktop shell ownership; no new authority, persistence scheme, or agent source dependency is introduced. Existing concurrent edits are preserved.

Continued authorization on 2026-10-15 requires actual non-GUI Python service, runtime and agent behavior, with separate native provider login per profile; Claude is selected. S07 repairs omission of the agent's already-declared Node/ACP runtime dependency closure. This Cadrumo integration uses the later accepted native-agent CMake/private-wheel topology, including shared application custom site-packages and colocated non-Python assets. The earlier agent record's separate complete interpreter/install and sibling placement are superseded only for this integration; that record remains unchanged for standalone agent shipping. Its pinned runtime dependency and user-only provider CLI constraints remain respected. Package-verification governs the unmodified built-package acceptance boundary and canonical-environment-application-internals governs image profiles. No new install topology or hosted proof bypass is introduced.

S08 was explicitly approved on 2026-10-15 when the user answered "Approve the proposed repair" for the external `Y:/code/cadrumo-agent-worktrees/main/.vault/adr/2026-10-15-cadrumo-integration-hosted-certification-bootstrap-adr.md`. It permits an ordinary-turn-proven, otherwise-admitted lane to use the normal hosted route while hosted-package certification is disclosed as pending in catalog, service status and frozen selection. This is a scoped change to the certification startup rule, not evidence that a hosted turn has passed. Credentials, installed-version checks, runtime authority, hosted layout and per-run permissions remain enforced. Only an actual completed package-backed hosted turn may earn the hosted proof record.

S09 responds to the user's 2026-10-15 constraint that other native builds cannot be paused. Existing accepted live-evaluation, package-verification and runtime-manager decisions already confine process control to owned artifacts and protect external installed/operator roots. The current quiescence helper incorrectly treats matching product identity as build ownership, including physical package copies outside the build. Correct that implementation boundary without changing package identity, runtime authority or proof policy; then verify independent-copy survival before resuming the manual login/model check during other builds.

S10 follows direct inspection of the completed product snapshot: the copied runtime imports a transport module that was added after the snapshot file census and is absent from the cohort. Existing package-verification and native-package-ci coverage requires a coherent delivered artifact. Check stability while capturing the existing source snapshot before any wheel build; preserve the existing allowance for later checkout edits after a coherent immutable snapshot has been captured. This is an implementation correction within the current packaging model. Do not accept or manually patch the failed cohort.

## Steps

- [ ] `S01` - Preserve actionable agent CLI and native startup errors and invocation timing; `src/cadrumo_agent_service/main.py, src/cadrumo_agent_service/service.py, src/cadrumo_agent_service/host/store_lifecycle.py, src/cadrumo_agent_service/host/tests/test_service_failure.py, native/application/src/diagnostics/service.rs, native/desktop frontend records and agent retry surfaces, owning tests`.
- [ ] `S02` - Coalesce sign-in observations and make agent retry supervision responsive and bounded; `native/desktop/src-tauri/src/shell/sign_in, native/desktop/src-tauri/src/agent/supervisor.rs`.
- [ ] `S03` - Verify corrected launch environment and service diagnostics in the rebuilt Windows package; `native/tests/environment_launch_probe.py, dev/runtime_lifecycle/agent_live.py, build/windows-x64 and build/windows-installers-x64, direct non-GUI service/runtime/provider-home and live-provider validation using manifest-verified independent copies`.
- [ ] `S04` - Diagnose and repair profile worker deadline cascades and distinguish ordinary client closes from refusals; `src/cadrumo/adapters/local_runtime/profile_worker_transport.py, src/cadrumo/adapters/local_runtime/server_connection_handling.py, src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py, owning tests`.
- [ ] `S05` - Preserve the declared external CLI binary directories across service, gateway and worker launches; `native/application-environment.toml, native/CONTRACT.md, native/platform/src/launch.rs, src/cadrumo_agent_service/host/launch_environment.py and tests, dev/packaging/native/environment_conformance.py and tests, packaged CLI resolution verification`.
- [ ] `S06` - Enable explicit provider-native sign-in in the isolated profile home through the agent-owned operator command; `src/cadrumo_agent_service/admin.py and service.py, adapters/agent_provider_catalog.py and sign-in capability/preparation tests, native/application-environment.toml and native/platform/src/launch.rs and native/CONTRACT.md, dev/packaging/native/application_environment.py and owning checks, cadrumo-agent CLI operator auth command and tests`.
- [ ] `S07` - Package the agent-declared pinned Node and Claude ACP runtime closure without any provider CLI and verify real packaged Claude startup; `create dev/packaging/native/agent_runtime.py and owning tests, native/agent/runtime.json, native/cmake/Agent.cmake and Packaging.cmake, dev/packaging/native/cmake_build.py and assemble.py and update_agent.py and owning package checks, src/cadrumo_agent_service/service.py and host/launch_environment.py and tests, native/tests/agent_smoke.py and its documented pyproject.toml subprocess grant, native/CONTRACT.md`.
- [ ] `S08` - Implement the user-approved hosted certification startup amendment while retaining ordinary proof and all runtime, sign-in and permission controls; disclose pending certification and earn the actual packaged hosted proof; `cadrumo-agent providers/lane_admission.py, API startup and catalog schemas, frozen run selection and tests, src/cadrumo_agent_service/adapters/provider_catalog_metadata.py and owning service contract tests, packaged direct service/model/tool verification`.
- [x] `S09` - Confine native build quiescence to verified build-owned image paths so independent physical package copies and external installed services remain live during parallel builds; `dev/packaging/native/process_quiescence.py, dev/packaging/native/tests/test_process_quiescence.py, native/CONTRACT.md, direct verified-copy isolation verification`.
- [x] `S10` - Reject a product source snapshot that changes during capture before building a mixed wheel cohort, preserving valid immutable snapshots after capture; `dev/packaging/native/product.py and owning snapshot-coherence tests, direct rebuilt package import and service verification`.

## Parallelization

S01 (root, Python diagnostics) and S02 (desktop worker, Rust sign-in and supervisor) may execute concurrently with disjoint ownership. S04 (runtime worker transport) may run concurrently with S01 and S02, with disjoint transport ownership. S03 follows all repairs; root owns package rebuilds, shared gates, ledger updates, commits, and final review.

Within S07, the runtime-closure helper and its tests may run independently of service environment composition. The root owns the CMake graph, assembly, shared metadata and package builds. The runtime helper worker owns only the new agent_runtime module, its tests and runtime pin declaration. The service worker owns only launch_environment and its focused tests. Workers preserve concurrent edits; the root integrates and reviews before rebuilding. Direct stage-directory process proofs wait for builds that own those images. After S09 verifies physical-copy isolation, proofs may use independent manifest-verified copies during other native builds.

S08 agent admission/catalog/frozen-selection work and Cadrumo service status projection may run concurrently with disjoint ownership. The agent worker owns external production contracts and their tests; the service worker owns service.py, service-owned status DTOs and focused tests. The root owns plan/ledger metadata, integration checks and native builds. Proof-client corrections remain confined to existing source-run qualification paths. No proof uses images owned by a running build; after S09 confirms isolation, independent verified copies remain eligible while build-owned images quiesce. The S09 worker owns process_quiescence.py, its tests and the focused contract wording; root owns the real copied-package isolation check.

S10 product snapshot guarding and its tests have one worker owner. Root owns integration, metadata, builds and direct package acceptance; no build overlaps edits to its product snapshot producer.

## Verification

Focused Python diagnostics and lifecycle tests, Rust supervisor and observation tests, configured lint and type checks, and the packaged environment launch probe must pass. Verify secrets remain scrubbed, stale sign-in is never authority, retry failures remain visible, and the packaged agent passes stores-state with the actual runtime environment.
