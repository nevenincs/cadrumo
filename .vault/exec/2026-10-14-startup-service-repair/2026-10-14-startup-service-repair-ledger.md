---
tags:
  - '#exec'
  - '#startup-service-repair'
date: '2026-10-14'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:2a9a59bbcc039bd4e2961bed5845554096fddcabcafe5d3e7cc988d51aca3ab7'
related:
  - "[[2026-10-14-startup-service-repair-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `startup-service-repair` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S04` `M` `src/cadrumo/adapters/local_runtime/profile_worker_transport.py`
- `S04` `M` `src/cadrumo/adapters/local_runtime/server_connection_handling.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py`
- `S04` `verify:` `focused transport and server tests (50)` -> `pass`
- `S04` `verify:` `focused KDF diagnostics cleanup exit tests (34)` -> `pass`
- `S01` `M` `src/cadrumo/adapters/local_runtime/agent_diagnostics.py`
- `S01` `M` `src/cadrumo/application/agent_host/store_lifecycle.py`
- `S01` `M` `src/cadrumo/core/diagnostic_log.py`
- `S01` `M` `native/application/src/diagnostics/service.rs`
- `S01` `M` `native/desktop/frontend/src/components/records/RecordRow.tsx`
- `S01` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S01` `verify:` `focused Python diagnostics lifecycle environment tests (83 original; new lifecycle regression passed in 138-test run)` -> `pass`
- `S01` `verify:` `diagnostic privacy and containment tests (34)` -> `pass`
- `S01` `verify:` `npm run check` -> `pass`
- `S01` `verify:` `Playwright agent refusal and explicit retry scenario` -> `pass`
- `S02` `M` `native/desktop/src-tauri/src/agent/supervisor.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/sign_in/mod.rs`
- `S02` `A` `native/desktop/src-tauri/src/shell/sign_in/reads.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/sign_in/process.rs`
- `S02` `M` `native/application/src/diagnostics/helper.rs`
- `S02` `verify:` `Rust sign_in focused tests (52 before helper outcome correction)` -> `pass`
- `S02` `verify:` `Rust agent supervisor tests (9 before review correction)` -> `pass`
- `S02` `verify:` `run-backend Unit Filter agent::supervisor final 10 tests` -> `pass`
- `S02` `verify:` `run-backend Unit Filter nonzero_exit_is_reported real helper regression` -> `pass`
- `S02` `verify:` `npm run check after helper outcome contract update` -> `pass`
- `S03` `verify:` `bundle.image from GUI verification session` -> `pass`
- `S03` `verify:` `bundle.environment-launch from GUI verification session` -> `fail`
- `S03` `verify:` `just check-code` -> `fail`
- `S03` `verify:` `just test-gate collection (run stopped after confirmed unrelated failure)` -> `fail`
- `S03` `verify:` `cmake app-agent incremental wheel update46 files (no dependencies or native rebuild)` -> `pass`
- `S03` `verify:` `ctest bundle.environment-launch20.42s after incremental agent update` -> `pass`
- `S01` `M` `src/cadrumo_agent_service/main.py`
- `S01` `M` `src/cadrumo_agent_service/service.py`
- `S01` `A` `src/cadrumo_agent_service/host/tests/test_service_failure.py`
- `S01` `verify:` `service unit suite 243 tests` -> `pass`
- `S01` `verify:` `service Windows integration suite 23 tests` -> `pass`
- `S01` `verify:` `manual packaged service admission and protected credential CAS set/remove/reset` -> `pass`
- `S02` `verify:` `native desktop Release compilation` -> `pass`
- `S03` `M` `dev/runtime_lifecycle/agent_live.py`
- `S03` `verify:` `live person driver and holder 20 unit tests` -> `pass`
- `S03` `verify:` `just check-registry-gate` -> `pass`
- `S05` `M` `native/application-environment.toml`
- `S05` `M` `native/platform/src/launch.rs`
- `S05` `M` `src/cadrumo_agent_service/host/launch_environment.py`
- `S05` `M` `src/cadrumo_agent_service/host/tests/test_launch_environment.py`
- `S05` `M` `dev/packaging/native/environment_conformance.py`
- `S05` `M` `dev/packaging/native/tests/test_environment_conformance.py`
- `S05` `verify:` `ctest platform.resolver including external directory gateway and worker regression` -> `pass`
- `S05` `verify:` `environment conformance and composer focused tests` -> `pass`
- `S05` `verify:` `focused Ruff rustfmt and ty` -> `pass`
- `S03` `verify:` `selected Codex user home login status exit0 and hosted profile home exit1` -> `pass`
- `S05` `M` `native/CONTRACT.md`
- `S05` `verify:` `native contract search-path paragraph reconciled with declared gateway and worker pass-through` -> `pass`
- `S05` `verify:` `final service unit and Windows integration suite 268 tests` -> `pass`
- `S05` `verify:` `environment conformance 59 tests` -> `pass`
- `S05` `verify:` `current Import Linter 24 contracts` -> `pass`
- `S03` `verify:` `cmake --build build/windows-x64 --config Release --target app-payload` -> `pass`
- `S03` `verify:` `staged python native/tests/environment_launch_probe.py after external-directory repair` -> `pass`
- `S03` `verify:` `temporary live package proof agent-live-5hu58oe3` -> `fail`
- `S03` `verify:` `fresh manual packaged service admin agent-manual-ob5uo5er` -> `pass`
- `S03` `verify:` `fresh manual packaged runtime shutdown agent-manual-ob5uo5er` -> `fail`
- `S03` `verify:` `pytest agent_live and session_holder unit tests (24)` -> `pass`
- `S03` `verify:` `live package proof agent-live-l2a5ehrv` -> `fail`
- `S03` `verify:` `external-root live proof agent-live-jzgehw20` -> `fail`
- `S06` `M` `src/cadrumo_agent_service/admin.py`
- `S06` `M` `src/cadrumo_agent_service/service.py`
- `S06` `A` `src/cadrumo_agent_service/host/tests/test_provider_sign_in_preparation.py`
- `S06` `M` `native/application-environment.toml`
- `S06` `M` `native/platform/src/launch.rs`
- `S06` `M` `dev/packaging/native/application_environment.py`
- `S06` `M` `dev/packaging/native/tests/test_application_environment.py`
- `S06` `verify:` `service and holder focused suite (282 tests)` -> `pass`
- `S06` `verify:` `native environment declaration unit tests (30)` -> `pass`
- `S06` `M` `src/cadrumo_agent_service/adapters/agent_provider_catalog.py`
- `S06` `M` `src/cadrumo_agent_service/adapters/tests/test_agent_provider_catalog.py`
- `S06` `verify:` `auth preparation catalog and parent-admin tests (34)` -> `pass`
- `S06` `verify:` `service and holder suite 289 tests` -> `pass`
- `S06` `verify:` `runtime cleanup and diagnostic suite 110 tests` -> `pass`
- `S06` `verify:` `independent corrective auth review` -> `pass`
- `S06` `verify:` `ctest platform.resolver 57 tests including operator auth environment` -> `pass`
- `S06` `verify:` `final Release app-payload assembly missing shared product receipt` -> `fail`
- `S01` `verify:` `just check-code final aggregate` -> `fail`
- `S06` `verify:` `new stdin shutdown tests Ruff ty and 8 focused subprocess tests` -> `pass`
- `S07` `A` `dev/packaging/native/agent_runtime.py`
- `S07` `A` `dev/packaging/native/tests/test_agent_runtime.py`
- `S07` `A` `native/agent/runtime.json`
- `S07` `M` `native/cmake/Agent.cmake`
- `S07` `M` `native/cmake/Packaging.cmake`
- `S07` `M` `dev/packaging/native/cmake_build.py`
- `S07` `M` `dev/packaging/native/assemble.py`
- `S07` `M` `dev/packaging/native/update_agent.py`
- `S07` `M` `dev/packaging/native/tests/test_update_agent.py`
- `S07` `M` `dev/packaging/native/tests/test_incremental_generation.py`
- `S07` `M` `dev/packaging/native/tests/test_assembly_refusals.py`
- `S07` `M` `src/cadrumo_agent_service/host/launch_environment.py`
- `S07` `M` `src/cadrumo_agent_service/service.py`
- `S07` `M` `native/tests/agent_smoke.py`
- `S07` `M` `pyproject.toml`
- `S07` `M` `native/CONTRACT.md`
- `S07` `verify:` `combined service and packaging unit suite 324 tests` -> `pass`
- `S07` `verify:` `service native process integration 24 tests` -> `pass`
- `S07` `verify:` `changed-file Ruff format and ty` -> `pass`
- `S07` `verify:` `CMake agent_project pinned Node and ACP construction` -> `pass`
- `S07` `verify:` `Release payload agent input-stability admission` -> `fail`
- `S07` `verify:` `Release app-payload=pass; packaged Node26.10.0 ACP0.85.1 exact-inventory smoke=pass; packaged launch environment probe=pass; auth providers and missing-root refusal` -> `pass`
- `S06` `verify:` `packaged person service admission catalog status sign_in preparation=pass; isolated Claude auth baseline exit1` -> `pass`
- `S03` `verify:` `final-copy real relay proof` -> `fail`
- `S07` `verify:` `independent runtime closure source review` -> `pass`
- `S03` `M` `src/cadrumo_agent_service/service.py`
- `S05` `M` `src/cadrumo_agent_service/main.py`
- `S05` `verify:` `final-package authority loss with parent stdin retained` -> `pass`
- `S05` `verify:` `final-package whole-tree authority-loss teardown` -> `fail`
- `S05` `verify:` `final-package retained-stdin authority-loss bounded whole-tree teardown` -> `pass`
- `S03` `M` `src/cadrumo_agent_service/main.py`
- `S03` `verify:` `packaged refusal-state authority-loss retained-stdin whole-tree shutdown` -> `pass`
- `S06` `verify:` `isolated interactive Claude login` -> `fail`
- `S03` `M` `.vault/audit/2026-10-14-startup-service-repair-audit.md`
- `S03` `verify:` `proposed hosted-certification decision review and owning checks` -> `pass`
- `S08` `M` `src/cadrumo_agent_service/service.py`
- `S08` `M` `src/cadrumo_agent_service/contracts.py`
- `S08` `A` `src/cadrumo_agent_service/host/tests/test_hosted_certification_status.py`
- `S08` `verify:` `service hosted-certification status regressions10=pass; scoped service Ruff format ty` -> `pass`
- `S08` `verify:` `entire agent service suite283` -> `pass`
- `S03` `M` `dev/runtime_lifecycle/proof_support.py`
- `S03` `M` `dev/runtime_lifecycle/tests/test_agent_live.py`
- `S03` `verify:` `full person proof driver suite17=pass; handoff client focused source checks` -> `pass`
- `S08` `verify:` `status-cache focused12=pass; entire service285=pass; integrated source review=pass; agent focused188` -> `pass`

## Notes

- `S04` Initial 10s worker stall and 30s cleanup cause remain unproven; typed request/action and cleanup subspan diagnostics support next reproduction.
- `S01` Broader code checks and final packaged verification pending. Unrelated concurrent changes preserved.
- `S02` Review correction preserves exhausted retries through failed status observations. New nonzero helper exit outcome regression and final native build pending.
- `S03` Original uppercase agent loglevel corrected: packaged stores-state/setup/current pass. Gateway/worker blocked by missing `lane_effort_control` import in bundled agent; GUI session owns incremental artifact investigation via build/message.txt. No dependency changes. User requires affected-artifact incremental builds only.
- `S03` Resolved stale mixed staged agent selection/effort import using existing app-agent target. Full real GUI sign-in verification handed to coordinating session through build/message.txt; historical KDF cleanup and worker stall remain evidence questions.
- `S01` Hosted gateway still refuses `hosted_lane_unproven;` provider CLI auth is absent from its hosted provider home.
- `S05` Refreshed package and live model turn pending. No hosted CLI credential provisioning was added.
- `S03` User 2026-10-15 explicitly requires separate provider sign-in in each Cadrumo profile CLI home; do not import external account credentials. Current `provider_sign_in` setting records a mode but performs no login.
- `S03` Fresh Release payload completed. Installed service.py and `launch_environment.py` text match source; byte hashes differ only due to newline normalization. Launch probe passes stores, standalone worker and environment sanitation while hosted gateway still truthfully refuses `hosted_lane_unproven.` Live proof retry ended before agent launch: runtime did not emit readiness within the existing deadline. No model turn or hosted authentication claimed.
- `S03` Real runtime, password-held CLI person, service admission, twelve-provider catalog/status, protected synthetic credential CAS set/remove/reset and asynchronous start acknowledgement completed. Both starts log `hosted_lane_unproven.` Despite temporary coordinator exit0, runtime stderr records ProfileWorkerRetireRequest timeout10s and native containment guard deadline; shutdown is failed evidence and is under investigation.
- `S03` External search-directory repair is now observed in the unmodified staged gateway: codex/cli selectable, gpt-6.1-sol admitted, packaged worker receives dispatch. Turn fails before a model response because the manual driver seats the isolated Codex runtime beneath the Git repository; provider refuses it. Tool relay also exceeds its30s start/list deadline. Driver now uses system temp outside repositories, preserving the guard; retry underway.
- `S03` Correction to temporary-root attempt: `dev._paths` intentionally redirects stdlib TEMP into the checkout. Default driver scratch remains build/acceptance; added explicit --scratch-parent so callers can select a provider-compatible external directory. Aborted ineffective agent-live-4mnry4z3 probe before proof; exact owned coordinator identity verified and all16 descendant/owner processes terminated and reaped. Retry uses user Temp/cadrumo-agent-acceptance, outside repositories.
- `S03` Explicit external scratch retry reaches `runtime_ready` but synthetic config profile edit exits1 with empty envelope. No model response or hosted authentication established. Incremental Luna review finds no new destructive-path defect; overall verdict PENDING. Runtime shutdown attribution remains unproven; no speculative native authorization changes applied.
- `S06` User continued explicit per-profile native CLI sign-in repair. Reuse provider-settings authority and agent project accepted provider-sign-in/provider-account decisions. Service prepares a fixed foreground agent auth login command with profile root and public external directories only; caller owns terminal and session tree. Prepared metadata is not authentication success. Agent owns provider-specific command/home mappings, direct inherited terminal IO and credential scrubbing. Packaged rebuild and interactive login remain pending.
- `S06` Independent review found credential kind does not imply an executable login action (for example another CLI lane had no handler). Corrected by querying agent-owned auth providers --json schema1 before CAS or launch preparation. Unsupported actions and API lanes now refuse without mode mutation. User selected Claude for the isolated login. Agent auth tests5 pass; package human login pending.
- `S06` Claude selected. Agent capability list prevents unsupported login preparation; actual isolated login and final package checks remain pending. Independent review identified broader existing admin dispatch deadline mismatch for follow-up.
- `S06` Concurrent Debug app-payload producer reset shared product output. Release retry queued behind that build. Agent wheel auth handler and MCP diagnostics text match current source. First new native auth test lacked the required OS environment fixture; corrected fixture, rerun passed.
- `S01` Aggregate fails reachability/symbol/export checks outside the agent paths; style, format, data format, dependency declarations, write-paths, docstring references and operation-contract manifest pass. Full output retained in .tmp/check-code-agent-auth.log.
- `S06` Corrected three type diagnostics in the new tests after aggregate gate; remaining aggregate findings include unrelated TUI journey/import/export paths.
- `S07` Runtime assets follow later accepted bundled Cadrumo topology; no SDK platform Claude CLI is included. Independent source review accepts scope; fresh Node/ACP package smoke and authenticated live proof remain pending.
- `S07` Separate agent project `provider_verify.py` changed during the full build; completion receipt correctly refused. Keep package verification pending and retry without bypassing source identity.
- `S07` Verified copy fd8f2dc987159da9516245819ff661bb95e4449b94fd8fd56c280d7cb38b3541 contains38171 files. Real package relay proof is running; hosted authentication and shutdown remain pending. No CLI credentials imported.
- `S06` Real package auth login script prepared for user-selected Claude in disposable profile-owned home; interactive login pending. No ordinary account imported. Full check-code passes nine categories including types; import/reachability/symbol/export gates fail in broader concurrently edited paths.
- `S03` Before model: packaged path validation refused stale external runner dotenv program outside verified copy. Job owner reaped all members. Source inspection also finds runner replaces exact handoff profile/root/scenario with fresh profile and later provenance rejects driver context; no false proof or weakened fresh-profile check applied. Hosted certification is circular under current accepted startup gate; proposed decision pending.
- `S07` Reviewer closes exact-inventory concern and finds no new high-confidence defect in service/runtime/Node-ACP repairs. Integrated review remains pending actual isolated login, real packaged relay effect, clean teardown and valid hosted certification decision/evidence. Handoff compatibility repair is within existing accepted package-verification coverage when fresh provenance is preserved.
- `S03` Prepared proposed external ADR 2026-10-15-cadrumo-integration-hosted-certification-bootstrap-adr for user review: ordinary-turn-proven lanes may attempt normal hosted route with certification explicitly pending; no false proof, test-only route or credential import. User approval requested under accepted decision approval contract. Existing hosted gate remains intact until authorized.
- `S05` Actual immutable package fd8f2dc987159da9: real runtime, held CLI person and admitted service; close person via public control while parent keeps both stdin pipes open. Holder exit0, service exit0; holder/runtime/service stderr empty. Outer owned job reports zero remaining members and coordinator0. This proves this refusal-state shutdown case; active model-worker retirement remains unproven.
- `S05` Correction to prior row: holder and service exit0 with retained parent stdin and all three stderr empty ARE observed; wrapper actually required cleanup of ONE remaining job member and forced exit1, not coordinator0. No clean-whole-tree claim. Add bounded child identity attribution and retry to distinguish real survivor from process-exit race.
- `S05` Fresh retry agent-authority-k62iosvi: actual holder and service exit0 while parent stdin pipes stay open; holder/runtime/service stderr empty. Immediately after coordinator exit one job member was already unavailable for identity lookup and disappeared naturally within the bounded2s reap grace. No forced cleanup, zero remaining job members, coordinator0. This proves refusal-state authority-loss shutdown; active model-worker retirement remains separate pending evidence.
- `S03` Step attribution correction: the preceding S05 authority-loss probe rows are S03 packaged verification evidence, not external-CLI propagation work. Actual final-copy retry agent-authority-k62iosvi: holder/service exit0, all stderr empty, no forced cleanup, zero members after bounded natural reap, coordinator0. Active-model retirement still pending.
- `S06` Before user completion, unrelated native Debug bundle build quiesced the held package session. Holder/runtime/service stderr empty, but coordinator detects lost holder/service and exits1; job cleaned allmembers. Prepared script invalidated to prevent stale login. No auth success claimed; reprepare only after build ends. Prior preparation and signed-out baseline remain valid scoped evidence.
- `S03` Independent review accepted scoped direction but required reconciliation of older nothing-before-proof consequence. Proposed external ADR now includes exact scoped replacement retaining ordinary proof/allothercapabilityrules; root reviewed it and owning checks pass. Status remains proposed; accepted body and product admission unchanged; user approval pending.
- `S08` User explicitly approved proposed hosted-certification startup repair on2026-10-15. Agent worker persists acceptance/exactolderwording reconciliation and implements ordinary-proof admission with distinct unknown/pending/proven catalog/frozen certification. Service worker projects actual authenticated live catalog certification into bounded adminstatus list. All runtime, credential, installed-version and permission controls remain. No successful hosted proof has been claimed.
- `S08` Only authenticated READY current-generation catalog can supply certification list; unknown default, invalid/stale/overlimit/duplicate/unavailable `returns[],` credentialstatus retained. Native admin JSON/structuralfrontend tolerateadditivefield. Actual packaged hosted/model verification awaits updated agent source and no concurrentbuild.
- `S08` Current service status projection passed all283 service tests in7.62s; test log20261015T084736.070515Z-pytest-68080-3c429b3f. Agent production admission/frozen-selection work and new packaged proof pending; source suite does not establish interactive login or hosted turn.
- `S03` Handoff preserves exact driver profile/root/scenario with distinct nonsecret held-session provenance; standalonefreshprofile path retained. Root caught Optional narrowing and forbidden source-client Cadrumo imports; both corrected. Marker check uses inventory-verified packaged interpreter with restrictedenv and10sbound, never sourceproductimports. Real package relay proof pending afternativebuild and updatedagent.
- `S08` Replaced status networkread with immutable5s currentgeneration snapshot fromnormal authenticatedcatalog; no newstatus HTTP latency versusnative6sdeadline. Reviewer finds no mustfix across ordinaryproof admission, catalog/frozen certification, cache and packaged marker helper. Release app-payload rebuild running; concurrentDebug build is read-only distribution preparation on separateDebugstage. No native live proof while builds remain.
