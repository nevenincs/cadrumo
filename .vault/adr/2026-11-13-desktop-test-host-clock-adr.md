---
tags:
  - '#adr'
  - '#desktop-test-host-clock'
date: '2026-11-13'
modified: '2026-11-13'
body_schema: 'body-v2'
body_hash: 'sha256:9a2f5c121cb182c5e9be517bd366c8acd3d723e0959c1a92d294c6742083c2c1'
related:
  - "[[2026-06-30-deterministic-output-replay-substrate-adr]]"
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-07-21-desktop-capture-harness-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-13-canonical-environment-application-internals-adr]]"
  - "[[2026-10-13-package-verification-adr]]"
  - "[[2026-07-01-determinism-replay-residual-adr]]"
  - '[[2026-06-30-deterministic-output-replay-substrate-research]]'
  - '[[2026-10-04-canonical-environment-reference]]'
---
# `desktop-test-host-clock` adr: `Test-host fixed clock for persona reproduction in the packaged window` | (**status:** `accepted`)

## Problem Statement

The persona table runs every persona's calculate, verify, export and local filing under `frozen_clock(as_of)` (`src/cadrumo/entrypoints/tests/persona_materialisation.py:438-444`, `_scenario`; `:2093`). The packaged window runs on wall-clock time. Date-gated stages therefore give different answers in the window. Observed on 2026-11-13: a 2025 Modelo 100 local filing in the window was refused with `REFUSED_MODELO_WORKFLOW_GATE` ("no filing obligation pending at the current date"), while the persona table files it at its instant 2026-02-16. A persona row cannot be reproduced in the built window until the window's tax work can run at the persona's instant. CADRUMO-PRIME ordered this decision on 2026-11-13 at 11:10 with five binding constraints, recorded under Constraints, and accepted it at 12:19 with the rulings recorded under Acceptance.

## Considerations

- The seam is a `ContextVar` (`src/cadrumo/core/time/clock.py:36`) read by `now()` (`:43`) and by `today_madrid()` (`:73`), the regulated-date authority under `2026-06-30-deterministic-output-replay-substrate-adr` (amendment 2026-07-14). `frozen_clock()` (`:141`) refuses under the live-test opt-in (`:121-137`). It is per context and per process: no value crosses a process boundary.
- Tax work runs in profile workers, not in the window or the runtime host. The worker starts with `python -I` (`src/cadrumo_runtime/adapters/profile_worker.py:205`, `:217`; `src/cadrumo_runtime/adapters/worker_arguments.py:11`), so it reads no ambient Python configuration.
- `child_environment` (`src/cadrumo/core/storage_environment.py:522`) strips every name with the product prefix (`:549`) and relays only the declared settings (`:473`, `:507`). A clock override reaches a worker only through an explicit relay.
- The Rust host starts the Python manager dispatcher with `-I` (`native/desktop/src-tauri/src/manager.rs:607`). No Rust-to-Python relay of a test setting exists. The runtime is launched by the shared native manager core with the strict environment: "no `CADRUMO_*` overrides" (`2026-10-04-runtime-manager-architecture-adr`, Constraints; `2026-10-13-canonical-environment-application-internals-adr`, constraint 6, Runtime images).
- Runtime authority timing already reads the seam: the worker lease expiry check (`src/cadrumo_runtime/adapters/worker_authorization_lease.py:386`) and the default `wall_clock` of `src/cadrumo_runtime/adapters/worker_authorization.py:123` and `src/cadrumo_runtime/adapters/profile_worker.py:81` all call `now()`. A process-wide freeze would compare a wall-clock lease against a past instant, so a lease would never expire. That weakens authenticated admission.
- Other direct wall-clock reads exist outside the seam: certificate validity and health (`src/cadrumo/adapters/outbound/aeat/auth/certificate.py:232`, `:496`, `:582`), the Retry-After parser (`src/cadrumo/adapters/outbound/aeat/browser/site_health_parsers.py:98`), the review response stamp (`src/cadrumo_runtime/host/session_hold_operations.py:410`) and the stall dump header (`src/cadrumo_runtime/host/worker_stall_watchdog.py:65`). The seam gate `src/cadrumo/core/tests/test_clock_seam_usage.py` scans `src/cadrumo` only (`2026-07-01-determinism-replay-residual-adr`, decision 2).
- The `native-automation` feature (`native/desktop/src-tauri/Cargo.toml:11`) already gates the test host's WebDriver plugin and nonce (`native/desktop/src-tauri/src/app.rs:138`, `:184`; `launch.rs:62`; `shell/automation_nonce.rs:10`, `:33`; `shell/automation_picker.rs:49`; `shell/picked_files.rs:164`, `:203`). The shipped image is `desktop-host-build` (`native/desktop/CMakeLists.txt:327`); the test host `desktop-packaged-host` (`:474`) is never distributed (`:450-453`).
- Two launchers create e2e roots: the automation session pins `CADRUMO_STORAGE_ROOT=<run>/storage` under the build's automation runs directory (`native/desktop/tests/automation/session.mjs:188-207`, run created at `:553`), and the persona lane uses `%LOCALAPPDATA%\Temp\cadrumo-e2e-<32 hex>` (`dev/desktop_agent_live/disposable_root.py:86-115`, root set at `dev/desktop_agent_live/desktop_processes.py:52`). Before this decision only the first supplied the automation nonce; under it both use WebDriver and the nonce.
- Python code ships in every image. Only Rust code can be compiled out of a release image.
- `2026-10-13-package-verification-adr` binding 1 says an application-behaviour test uses no build feature absent from shipped configurations. The test host already carries two such features.

## Considered options

- **A host-admitted, operation-scoped fixed clock relayed through a declared launch slot (chosen).** Reuses the seam, keeps authority timing on wall time, and compiles the admission out of release images.
- **Freeze the whole worker and runtime processes at entry.** Rejected: lease expiry, session hold and response correlation read the same seam (`worker_authorization_lease.py:386`), so authority would be frozen with the tax clock.
- **Change the operating-system clock of the test machine.** Rejected: it moves certificate validity, TLS, token lifetimes and every other process on the host, and it is not reproducible per run.
- **Let the window send an as-of date with each operation request.** Rejected: it makes the reference date a client-supplied request field reachable in shipped builds, which turns a test lever into product authority.
- **A second clock seam for the window.** Rejected by PRIME constraint 4; two consulted clocks would also drift.
- **Compare the window only on rows that are not date-gated.** Rejected: the refused local filing is exactly the stage the table must prove.

## Constraints

Binding (PRIME, 2026-11-13 11:10):

1. **Test host only.** Admission and relay of the fixed clock exist only in Rust code compiled with the `native-automation` feature. They are compiled out of `desktop-host-build` and of every released manager or runtime image. The shared manager core receives the capability only through a feature that the test host forwards; no released image enables it.
2. **Refused otherwise, with tests.** A build without the feature has no code that reads the override. A test proves that such a host starts the runtime with no fixed clock even when the launcher sets the override. In Python, the runtime host and the profile worker refuse to start when the override arrives without the admission conditions below. Tests prove each refusal.
3. **Bound to the e2e storage root.** The override names the storage root it is for. The host refuses unless that root equals its pinned absolute `CADRUMO_STORAGE_ROOT`, is not the per-user default root of the channel, and is an e2e root created by one of the two launchers. Python repeats the root-equality and default-root checks. An override aimed at any other root is refused.
4. **One seam.** The fixed clock is `frozen_clock()` of `src/cadrumo/core/time/clock.py`. No second frozen-instant variable, no second `now()` and no clock field on operation requests are added.
5. **Visible.** The window shows that the clock is fixed and at which instant, using words the backend serves. The fact shown comes from the Python side that activated the clock, not from the Rust admission alone.

Further binding commitments of this decision:

6. **Authority stays on wall time.** Login, session, lease, admission, interaction-response and journal timing never follow the fixed clock. Authority reads use an explicit wall-clock read that `frozen_clock()` cannot reach.
7. **Scope is the operation's tax work.** In the profile worker the fixed clock is active only around the execution of a registered operation's application work, the same work the persona table freezes. The runtime host never enters `frozen_clock()`.
8. **One instant per runtime lifetime.** The instant is fixed at runtime start. No request can change it; a new instant needs a new runtime start.
9. **Not product authority.** A result produced under a fixed clock is persona-reproduction evidence. It is not evidence of shipped behaviour at the wall date. No fixed-clock run contacts AEAT.

10. **Always the test host's own manager core.** A `native-automation` test host always hosts the shared manager core for its own e2e root and never defers to an installed manager.
11. **Always the nonce.** Admission always requires a valid automation nonce, on every launcher path.
12. **A fixed-clock root never runs on wall time.** Once a root has been admitted under a fixed clock, every later start on it without an admitted fixed clock is refused.

Items marked *hypothesis* below may change within these constraints.

## Implementation

We will add a test-host-only fixed clock. The automation launcher requests an instant for one e2e root. The `native-automation` test host admits it and relays it to the runtime through a declared launch slot. The runtime host relays it to each profile worker. The worker runs each registered operation's application work under `frozen_clock(instant)`. Authority timing moves to an explicit wall-clock read. The window shows a served fixed-clock notice.

**Launcher.** The automation session and the persona lane set two variables: the instant as a UTC ISO 8601 value, and the absolute storage root the instant is for. The persona lane's instant is the persona's `as_of`. The names are `CADRUMO_FIXED_CLOCK_INSTANT` and `CADRUMO_FIXED_CLOCK_ROOT`. They are declared in `native/application-environment.toml` and its generated projection, never as `Settings` fields, so no settings path can read them. Both launchers also supply the automation nonce and a WebDriver port; the persona lane drives the window over WebDriver with the nonce.

**Rust admission (feature `native-automation` only).** The test host reads the two variables at start. It admits them only when a valid automation nonce and a WebDriver port are present, the instant parses as UTC, the root equals the pinned `CADRUMO_STORAGE_ROOT`, the root is not the channel's per-user default, and the root is an e2e root. A malformed or unbound value refuses the launch with a typed error, as a malformed nonce does today (`native/desktop/src-tauri/src/shell/automation_nonce.rs:23-27`). An e2e root is recognized by the launcher's path shape (`<runs>/run-*/storage` or `cadrumo-e2e-<32 hex>`) together with its state at first admission: it is empty, or it already carries the fixed-clock marker. On first admission the host writes the marker, a runtime-owned file member under `.runtime/` that `2026-08-03-canonical-storage-management-adr` declares (amendment 2026-11-13). The marker records the admitted instant. Any other root is refused.

**Relay to the runtime.** The admitted instant and root reach the runtime through a declared launch slot of the runtime launch profile. Only code compiled under the forwarded feature in the shared manager core fills it. The strict profile is otherwise unchanged. The test host always hosts the shared manager core for its own e2e root and never defers to an installed manager (constraint 10). If a manager without the feature nevertheless owns supervision, the slot stays empty; the runtime then refuses a marked root (constraint 12), or, on a fresh root, runs on wall time, and the launcher detects that through constraint 5 and fails the run before driving.

**Python runtime host.** At process entry the runtime reads the slot once. It refuses to start, with a typed refusal the window reports as runtime unavailable, when only one of the two values is present, the instant is not UTC, the root differs from its pinned root, the root is the channel default, the live-test opt-in is set (the existing `frozen_clock` refusal, `src/cadrumo/core/time/clock.py:121-137`), or the root carries the fixed-clock marker and no admitted fixed clock arrived. Otherwise it records the admitted instant, never enters `frozen_clock()` itself, and serves the instant on its status projection.

**Relay to workers.** `worker_launch_environment` (`src/cadrumo_runtime/adapters/profile_worker.py:476`) relays the two values only from the runtime's admitted state, never from the environment it received. The relay is a dedicated helper beside `child_environment`, not an addition to `relayed_setting_names()`, so the `OPERATOR` profile used by other children never relays them. The worker repeats the runtime's checks at entry and refuses to start on any failure.

**Worker scope.** The worker enters `frozen_clock(instant)` around the registered operation's application execution. The scope ends are pinned in code at the supervisor's handler invocation. Journal, guard and receipt stamps are written outside it and stay on wall time. Authority rechecks inside the handler are covered by the next paragraph.

**Wall-clock reads that must not follow the override.**

- Lease expiry (`src/cadrumo_runtime/adapters/worker_authorization_lease.py:386`) and the default `wall_clock` of `src/cadrumo_runtime/adapters/worker_authorization.py:123` and `src/cadrumo_runtime/adapters/profile_worker.py:81` move from `now()` to an explicit wall-clock read. Reason: authority must expire on real time; a frozen past instant would keep a wall-minted lease alive.
- `src/cadrumo_runtime/host/session_hold_operations.py:410` (`responded_at`) stays on wall time. Reason: it stamps an interaction response the runtime correlates with lease and session state.
- `src/cadrumo_runtime/host/worker_stall_watchdog.py:65` stays on wall time. Reason: it is a diagnostic stamp beside a stall timer; a fixed instant would make dumps unorderable.
- `src/cadrumo/adapters/outbound/aeat/auth/certificate.py:232`, `:496`, `:582` stay on wall time through their existing `now=` injection. Reason: certificate validity is a fact about the real certificate at the moment of use; a past instant could report an expired certificate as valid. Persona runs use no live certificate.
- `src/cadrumo/adapters/outbound/aeat/browser/site_health_parsers.py:98` stays on wall time. Reason: Retry-After paces a real network peer.
- Everything that reads `now()` or `today_madrid()` inside the worker's operation scope follows the override. This covers the date gates the persona table freezes, including the Modelo workflow gate.

*Hypothesis:* the explicit wall-clock read is a function in `src/cadrumo/core/time/clock.py` that returns `datetime.now(tz=UTC)` and is documented as authority timing only. It holds no state and no frozen instant, so it is not a second seam. The seam gate gains a scan of `src/cadrumo_runtime` that classifies each clock read as seam or wall and refuses an unclassified one, so a new authority read cannot silently follow the override.

**Window notice.** While the runtime serves a fixed instant, the window shows a persistent notice that the clock is fixed and at which instant. The words come from the backend through `dev.locales` keys in every supported locale; the window computes no date. The automation session reads the served instant and fails the run unless it equals the requested instant.

**Required tests.**

- Rust: a build without the feature starts the runtime with an empty slot although the variables are set. The test host refuses a missing or malformed nonce, a malformed instant, a root mismatch, the default root, a root outside the launcher path shapes, and a non-empty root without the marker.
- Python refusals: the runtime and the worker each refuse a lone variable, a non-UTC instant, a root mismatch, the default root, the live-test opt-in, and a marked root started without an admitted fixed clock.
- Wall lease expiry: a lease minted on wall time expires on wall time while the operation runs under a fixed past instant.
- Wall stamps: journal, guard and receipt stamps of an operation run under a fixed past instant carry wall time.
- Wall-read gate: the `src/cadrumo_runtime` scan refuses an unclassified clock read, with a positive control.
- Parity: the Modelo workflow gate inside a fixed scope gives the persona table's answer for the same instant.

## Rationale

The knockout is authority. A fixed clock that also fixes lease and session timing weakens authenticated admission, and the lease check already reads the seam. Scoping the freeze to the operation's tax work, as the persona table does, and moving authority reads to an explicit wall read gives the window the persona table's dates without changing what admits or expires a session.

The launch-slot relay fits `2026-10-13-canonical-environment-application-internals-adr` constraint 7: launch parameters are values known only at launch, supplied by the parent within declared slots. Python ships in every image, so the release guarantee must be structural: the slot filler is compiled out of release images. The Python refusals guard against a stray or mismatched value, not against a release image filling the slot.

Serving the instant to the window meets PRIME constraint 5 and also proves activation. The launcher reads the same served fact the operator sees, so a run under a manager without the feature fails before it produces a misleading row.

## Consequences

- Date-gated persona rows become comparable between the persona table and the packaged window, including local filing.
- Accepted risk (PRIME, 2026-11-13 12:19): a Python reader and relay ship in every image. They stay inert because no released native launcher fills the slot and every Python entry refuses unbound values. A same-account process that can set a runtime's launch environment could still fix the clock for a non-default root; such a process already controls that runtime.
- Data written under a fixed clock carries past timestamps. A root used under a fixed clock never later runs on wall time; the `.runtime/` marker enforces this.
- Authority reads in `src/cadrumo_runtime` gain a classification gate. New authority timing must choose the wall read deliberately.
- Fixed-clock results cannot claim shipped application behaviour; `2026-10-13-package-verification-adr` needs the scoped amendment below.
- Reconsider if: an installed release manager must supervise e2e roots (the slot would then need a released filler, which this decision forbids); the persona table changes its frozen scope; one runtime needs several instants; or the worker's authority rechecks cannot be separated from the operation scope.

## Amendments to accepted records

Applied with this record's acceptance, in the same change, as in-place insertions that name this record.

- `2026-06-30-deterministic-output-replay-substrate-adr`, Implementation, Clock seam: after "the contextvar is never set in any production path." add "The one exception is the test-host fixed clock of `2026-11-13-desktop-test-host-clock-adr`: a profile worker of a runtime started by a `native-automation` test host for an e2e storage root sets it around a registered operation's application work. Authority timing reads the wall clock, never the seam." Consequences: after "or the seam rots into a backdoor." add "The test-host exception keeps this guard structural: no released native image fills the fixed-clock launch slot."
- `2026-10-04-runtime-manager-architecture-adr`, Constraints, Identity and privilege: "It launches the runtime with an allow-list environment that has no `CADRUMO_*` overrides." becomes "It launches the runtime with an allow-list environment that has no `CADRUMO_*` overrides, except the fixed-clock launch slot that only a manager core compiled with the `native-automation` feature fills (`2026-11-13-desktop-test-host-clock-adr`)."
- `2026-10-13-canonical-environment-application-internals-adr`, constraint 6, Runtime images: after "as `2026-10-04-runtime-manager-architecture-adr` binds ("no `CADRUMO_*` overrides")." add "The runtime launch profile declares one test launch slot, the fixed clock of `2026-11-13-desktop-test-host-clock-adr`, filled only by native code compiled with the `native-automation` feature and relayed to profile workers only from the runtime's admitted state." The Kept out bullet on development and test names gains "; the fixed-clock slot enters only under `2026-11-13-desktop-test-host-clock-adr`".
- `2026-10-04-canonical-environment-adr`, Constraints, Resolve once, pin, inherit: after "beyond the pinned set the contract declares." add "A test launch slot the contract declares, such as the fixed clock of `2026-11-13-desktop-test-host-clock-adr`, is filled only in images built with the feature that fills it."
- `2026-10-13-package-verification-adr`, binding 1: "It never imports a source checkout, a development `.venv`, or a build feature absent from shipped configurations." becomes "It never imports a source checkout or a development `.venv`. It uses a build feature absent from shipped configurations only through the packaged test host (`desktop-packaged-host`); a claim made under such a feature, including the fixed clock of `2026-11-13-desktop-test-host-clock-adr`, names that feature and is not a claim about the shipped image."
- `2026-07-01-determinism-replay-residual-adr`, Implementation, Seam-coverage gate: after "walks `src/cadrumo` production modules" add "and, under `2026-11-13-desktop-test-host-clock-adr`, classifies every clock read in `src/cadrumo_runtime` as seam or wall".
- `2026-08-03-canonical-storage-management-adr`, new section "Amendment 2026-11-13 - fixed-clock marker under `.runtime/`": declares one runtime-owned file member under `.runtime/` that records an admitted fixed clock. Only a `native-automation` test host writes it, only for an e2e root this record admits; it carries no variable and no settings field, is not reclaimable, and makes the root refuse every later start without an admitted fixed clock.
- `2026-07-21-desktop-capture-harness-adr` governs the Claude Desktop real-client capture, not Cadrumo's window. It needs no amendment. This record follows its isolated per-run root posture.

## Acceptance

Accepted 2026-11-13 at 12:19 by CADRUMO-PRIME under the ADR acceptance the operator delegated to PRIME, with these rulings on the questions the proposal left open:

1. A `native-automation` test host always hosts the shared manager core for its own e2e root and never defers to an installed manager. Development and CI never register boot or login startup (rule 04). If a manager without the feature owns supervision, the run fails before driving.
2. An e2e root is recognized by launcher path shape plus emptiness or the marker at first admission. The marker is a member under `.runtime/`, declared by the 2026-11-13 amendment of `2026-08-03-canonical-storage-management-adr`. A root once used under a fixed clock never runs on wall time.
3. The automation nonce is always required.
4. The inert Python reader and relay in every image are an accepted risk; every Python entry refuses unbound values, with tests.
5. The end of the worker's frozen scope is pinned in code at the supervisor's handler invocation, with a wall-lease-expiry test and a test that journal, guard and receipt stamps stay on wall time.
6. The names are `CADRUMO_FIXED_CLOCK_INSTANT` and `CADRUMO_FIXED_CLOCK_ROOT`, declared in `native/application-environment.toml` and its generated projection, never as `Settings` fields.

Still open within the constraints: the name and placement of the explicit wall-clock read, and whether a marked root admits a later instant different from the one its marker records. Acceptance records the decision; it is not evidence that any of it is built. Code follows in units handed to INTEGRATOR, the Python refusals and the wall-read gate first.
