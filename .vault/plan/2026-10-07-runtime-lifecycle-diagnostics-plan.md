---
tags:
  - '#plan'
  - '#runtime-lifecycle-diagnostics'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:b78c17976932937df61ca60bf805cc541e88fe2604f6a2e9a5635fd4dc413af2'
---

<!-- RETIRED: S08 -->

# `runtime-lifecycle-diagnostics` plan

## Description

Approved 2026-10-07. The user explicitly authorized logging enrichment and wiring delegated to GPT-6.1 Sol xhigh agents, then directed the root agent to implement desktop runtime lifecycle management while another session owns the manager implementation.

On 2026-10-07 the user clarified the missing stable launcher: "Handle the desktop integration here; flag the launcher dependency". Deliver the bounded desktop startup/retry/cleanup integration and its verification here. Version-independent discovery, newest-complete-version selection and installed upgrade acceptance remain an explicit external release prerequisite; this clarification does not exempt current-package dispatch from the governing architecture. S04 remains open for that integration prerequisite rather than claiming installed lifecycle completion.

Reuse the accepted runtime-manager architecture and supervisor contract for lifecycle ownership, desktop-shell for host/log presentation and payload exclusion, and canonical-environment for path and environment authority. No new costly decision: add diagnostic metadata to the existing log projection and implement the already accepted desktop manager-start responsibility. Preserve private-data scrubbing, opaque diagnostic correlation distinct from credentials, and connection-only CLI/TUI/MCP clients. The desktop never stops or owns the runtime. Existing version-independent installed-entry discovery must be respected; report missing upstream interfaces without inventing runtime ownership.

The separate manager session retains its active implementation files. This work adds desktop integration and diagnostic plumbing with disjoint ownership and coordinates any manager seam before mutation. Discovery used targeted fallback after the semantic service refused startup due to another process owning its model stack.

## Steps

- [x] `S01` - Emit structured redacted Python process and attempt diagnostics across TUI, connection and runtime lifecycle; `src/cadrumo/core/logging.py, diagnostic_log.py, startup_phase_log.py, adapters/local_runtime/startup.py, entrypoints/tui/, entrypoints/runtime/, owning tests`.
- [x] `S02` - Preserve safe native process attribution and failure detail in lifecycle diagnostic events; `native/application/src/{diagnostics,error,process}/**, native/application/tests/diagnostics.rs, native/desktop/src-tauri/src/{startup_logging.rs,main.rs,environment.rs,terminal/**,shell/sign_in/mod.rs,shell/sign_in/process.rs}`.
- [x] `S03` - Parse and display diagnostic context and consistent timestamps across backend log sources; `native/desktop/src-tauri/src/logs/, frontend log contract/components/filtering/tests`.
- [ ] `S04` - Wire desktop-owned manager discovery and shell dispatch with truthful startup and retry outcomes while preserving independent runtime ownership; `native/desktop/src-tauri manager integration, host startup, shell sign-in, frontend manager remedy, platform helpers and owning tests`.
- [x] `S05` - Harden and measure concurrent startup, helper shutdown, package and environment refusal, relocation and diagnostic resource bounds with root-owned architectural review; `native/desktop/src-tauri/src/manager.rs and owning tests, native/application binary admission and diagnostics with owning tests, Python diagnostic concurrency tests, frontend manager scenarios, scoped measurement artifacts`.
- [x] `S06` - Persist safe manager lifecycle diagnostics and bound supervisor queues without delaying shutdown; `native/manager startup/background/supervision/diagnostics and owning tests, native/application diagnostics sink and closed schema, canonical contract projection`.
- [ ] `S07` - Expose manager records in the desktop log viewer and repair empty-root packaged profile acceptance ordering; `native/desktop environment and log consumer, owning frontend and backend tests, packaged sign-in/runtime fixtures, rebuilt package verification evidence`.
- [x] `S09` - Record WebView process failures with safe typed diagnostics and preserve failed-run evidence; `native/platform desktop WebView callback, native/application diagnostics, desktop shell and host log projection, owning tests`.
- [x] `S10` - Prevent background profile reads from rejecting an explicit sign-in while bounding helper admission and shutdown waits; `native/desktop shell sign-in child admission and owning subprocess tests, native application CLI busy diagnostic code`.
- [x] `S11` - Explain login-witness shutdown with bounded inventory and observation diagnostics without changing authority policy; `src/cadrumo/entrypoints/runtime/profile_connections.py, fixed-field allowlist in src/cadrumo/core/diagnostic_log.py, and owning diagnostic tests`.
- [x] `S12` - Repair fresh Windows SDK provisioning after the generated destination is reset; `dev/packaging/native/platforms/windows.py provision_sdk and focused package regression tests`.
- [ ] `S13` - Attribute runtime startup, profile creation, sign-in and shutdown latency with bounded phase and CPU measurements before optimizing; `native/desktop/src-tauri/src/shell/sign_in, native/application/src/diagnostics, native/manager/tests/runtime_identity.rs, native/desktop/tests/packaged, runtime latency evidence`.
- [x] `S14` - Remove redundant schema binding compilation and background-read serialization from sign-in without weakening validation or increasing timeouts; `src/cadrumo/application/operations/registry.py and owning tests, native desktop sign-in process lanes and frontend sequencing, app shutdown and owning tests`.
- [x] `S15` - Defer unused Google export implementation imports to their operation execution boundary and measure startup CPU and dependency closure; `src/cadrumo/entrypoints/operation_composition.py, google_review_operation_composition.py, owning entrypoint tests and guarded performance evidence`.

## Parallelization

The queue hardening initially tracked as S08 is consolidated into S06: the bounded event channel, loss counter, persisted diagnostic schema and shutdown drain form one buildable producer change. S08 is retired without execution rows.

The user subsequently supplied this machine's signed-in Session 1 for acceptance, explicitly noting that the machine is not disposable. Root will run the existing interactive harness with a fresh explicit storage root, without changing existing profiles or login registration. A one-shot current-user interactive task can launch the harness from Session 0 and is removed after use. This is isolated application acceptance, not installed default-root manager or upgrade acceptance.

For S06-S07 the operator handed remaining work to this session ("it is all yours!"). The previous implementation and manager startup are now committed and the shared index lock has cleared. Root retains architectural review and package validation; Sol 6.1 workers implement manager diagnostic production, desktop consumption, and isolated acceptance fixture ordering with disjoint write ownership. Generator changes belong to the diagnostic producer and are coordinated with the consumer. The existing distribution-owned versioned-install prerequisite remains unresolved; this work does not invent a registry or installer discovery contract. Root's tool host is Session 0; the operator-authorized Session 1 harness supplies isolated interactive acceptance on this same machine.

S09 follows an actual WebView crash during isolated acceptance. Root defined an observation-only ProcessFailed callback carrying closed kinds/reasons and numeric OS metadata, without paths, page data, automatic reload or lifecycle policy changes. The Sol 6.1 native-logging worker owns the platform callback, application fact, shell hook and owning projection/tests. Its compiler-only manager Event initializer is coordinated with the frozen S07 consumer. The Sol 6.1 package worker owns bounded acknowledged VT observation in the harness. Root owns per-check/startup timing, failed-run artifact retention, process-resource observation, plan/ledger and integrated architectural review. These assignments use disjoint files except explicitly coordinated initializers; no worker runs the interactive harness or changes login registration.

S10 follows the fourth isolated run's sign-in queue refusal. Root identified that the single helper slot rejects mutations even while occupied by an ordinary read. The native worker owns the bounded admission implementation and real-child regressions: one pending mutation may wait at most 30 seconds behind a read, receives priority over later reads, and cannot queue behind another mutation; at most eight reads may wait, retaining their existing wait through slow profile creation. No password retry is introduced. Shutdown must wake waiters and retain unsettled child ownership. Root owns review and interactive validation; the package worker's measured idle-observer tuning is confined to its harness files.

For S05 the user clarified that GPT-6.1 Sol agents may implement logging and coding work, while genuine architectural review belongs to root. Root owns lifecycle concurrency, cancellation, package admission, shutdown fixes, test strategy and integrated review. Narrow worker assignments cover Python formatter bounds and correlation, native diagnostic sink recovery, and browser lifecycle regression tests. The manager implementation remains owned by the separate session; root tests its existing fixture contract without editing its source.

S01 (Python logging), S02 (native diagnostics), S03 (log parser/viewer), and S04 (desktop lifecycle) may run concurrently after agreeing the additive event and log metadata contracts. S01 owns Python source and tests. S02 owns native/application diagnostics, process and safe error modules. S03 owns desktop logs modules and log-specific frontend components/contracts/tests. S04 is root-owned desktop manager dispatch, host startup and sign-in integration with platform helpers if needed. Serialize shared frontend contract edits between S03/S04. No worker changes existing manager lifecycle files. Root owns plan, ledger, commits, shared checks and final integrated review. Workers run independent focused tests and report evidence. Existing unrelated changes remain untouched.

## Verification

S11 follows a fifth-run shutdown whose warning omitted the inventory state. Root preserves the existing conservative authority policy and owns interpretation. The Sol 6.1 native-logging worker owns only the runtime warning's bounded counts, completeness and observation timing plus diagnostic tests. No identity values, native objects or exception payloads enter those records. The package worker separately owns fixed-label fixture phase timings and closed lifecycle summaries in failed-run evidence; root runs the integrated tests and resource observers.

Prove actual file logging retains scrubbed process/attempt/outcome/refusal metadata, connection exceptions produce failure outcomes, and TUI registration/admission/login boundaries are distinguishable. Check secrets and private payloads never enter records. Parse canonical timestamps and legacy rotations truthfully; verify viewer timezone, process identity, metadata filtering/copy, multiline and partial-line behavior. Native lifecycle failures retain safe OS codes and child attribution without captured output. Desktop launch tests cover missing/present manager, verified package admission, unmanaged roots, dispatch failure, repeated requests and window shutdown independence. Reuse focused passing tests and run configured formatting/lint/type/import checks for touched areas. Package/interactive limitations are recorded separately from code correctness. Final review traces the integrated producer/parser/viewer and desktop/manager boundary; completion requires all checks applicable to changed code and no unresolved high findings.
