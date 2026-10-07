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
body_hash: 'sha256:4a6070ceff04f73ffa86bb32cb17f9d97aa89adb3476c2d4bed621f391441573'
---

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

## Parallelization

For S05 the user clarified that GPT-6.1 Sol agents may implement logging and coding work, while genuine architectural review belongs to root. Root owns lifecycle concurrency, cancellation, package admission, shutdown fixes, test strategy and integrated review. Narrow worker assignments cover Python formatter bounds and correlation, native diagnostic sink recovery, and browser lifecycle regression tests. The manager implementation remains owned by the separate session; root tests its existing fixture contract without editing its source.

S01 (Python logging), S02 (native diagnostics), S03 (log parser/viewer), and S04 (desktop lifecycle) may run concurrently after agreeing the additive event and log metadata contracts. S01 owns Python source and tests. S02 owns native/application diagnostics, process and safe error modules. S03 owns desktop logs modules and log-specific frontend components/contracts/tests. S04 is root-owned desktop manager dispatch, host startup and sign-in integration with platform helpers if needed. Serialize shared frontend contract edits between S03/S04. No worker changes existing manager lifecycle files. Root owns plan, ledger, commits, shared checks and final integrated review. Workers run independent focused tests and report evidence. Existing unrelated changes remain untouched.

## Verification

Prove actual file logging retains scrubbed process/attempt/outcome/refusal metadata, connection exceptions produce failure outcomes, and TUI registration/admission/login boundaries are distinguishable. Check secrets and private payloads never enter records. Parse canonical timestamps and legacy rotations truthfully; verify viewer timezone, process identity, metadata filtering/copy, multiline and partial-line behavior. Native lifecycle failures retain safe OS codes and child attribution without captured output. Desktop launch tests cover missing/present manager, verified package admission, unmanaged roots, dispatch failure, repeated requests and window shutdown independence. Reuse focused passing tests and run configured formatting/lint/type/import checks for touched areas. Package/interactive limitations are recorded separately from code correctness. Final review traces the integrated producer/parser/viewer and desktop/manager boundary; completion requires all checks applicable to changed code and no unresolved high findings.
