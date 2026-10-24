---
tags:
  - '#audit'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:f631c8a2ebd5aa5b41cdcf54c5b0df64c69fdaccbb6e36c49d20572c536229e2'
related:
  - "[[2026-10-24-rust-component-provisioning-plan]]"
  - "[[2026-10-24-rust-component-provisioning-adr]]"
---
# `rust-component-provisioning` audit: `Rust component provisioning review`

## Scope

Phase-close review of P01 ("Engine core: pins, transfer, states and plan") of `2026-10-24-rust-component-provisioning-plan`, plus the Python withdrawal Step P05.S16. Commits reviewed: 61e0600637 (S01), 67cd87f077 (S02), 606c8bdef5 (S03), 1e6383dc63 (S04) and c002a7769a (S16). The base is each commit's parent and the target is HEAD c002a7769a. `native/application/src/provisioning/network.rs`, `mod.rs` and `native/application-environment.toml` are byte-identical at HEAD to 606c8bdef5: the foreign delete in e7301548b6 was fully undone by 70ae70915f. Uncommitted scope: the worktree holds a foreign, uncommitted edit to `src/cadrumo/application/dependency_wording.py`, outside these commits and not reviewed.

Governing contracts: `2026-10-24-rust-component-provisioning-adr` constraints 1, 3 to 5, 10 and 11, and `2026-10-18-dependency-provisioning-unified-setup-adr` D2, D4, D5, D6, D9 with its 2026-10-19, 2026-10-21 and 2026-10-24 amendments. Evidence came from `2026-10-24-rust-component-provisioning-reference` and the plan's ledger.

The pins are genuine. The program pins in `src/cadrumo/_data/dependencies/local_ai_program.toml` match, for all four assets, the size and SHA-256 that the publisher's GitHub release listing for v0.40.10 publishes. The registry manifests of `qwen3:1.7b` and `qwen3-vl:2b` hash to the pinned `manifest_digest`, and their layer-plus-config sizes equal the pinned `download_bytes`. The model pins were moved byte for byte out of `src/cadrumo/core/model_catalogue.py`, which now reads the table and keeps no copy. No multi-GB archive was downloaded.

The plan digest has an independent oracle. The Python `dependency_plan_digest` (`src/cadrumo/application/dependency_contracts.py:647`), applied to the same entries, gives `df55d305...2c08`, the value `native/application/src/provisioning/plan.rs:360` asserts.

Python provisioning after c002a7769a. No product Python path still downloads, installs, extracts or removes a component, and none launches the browser for verification:
- The composed `dependencies.*` registry binds only refusing effect ports and `WithdrawnSetupItem`.
- `local-reader.provision` refuses `start` and `remove` at access.
- The CLI provision verbs, the TUI, MCP and the desktop relay all reach those registered operations.
- `fetch_runtime_model`, the vendor installer, the archive fetch and server, and the package-manager install now have no live product caller.

One residual capability and one misreport are recorded below.

## Findings

### transfer-source-fallback | high | A final failure on one archive source never gives way to the next source

`native/application/src/provisioning/transfer.rs:181-186` returns at the first non-transient failure from any source. Any of these on the first source therefore ends the transfer without trying the vendor's next source:
- a 404 or 416;
- a TLS refusal;
- a final proxy-tunnel status other than 403 or 407;
- on Windows, a name that does not resolve (`connect_failure` makes WSAHOST_NOT_FOUND final at `transfer.rs:469-471`, while the same fault on Linux and macOS is transient and does fall through).

The 2026-10-21 hop rule, which the Rust ADR keeps (pins and hop rules stand), says only `damaged_download` and `blocked_by_network` stop other sources, and that a network failure on one source gives way to the vendor's next source. The Python fetch this replaces did that: `src/cadrumo/adapters/outbound/browser_runtime/archive_fetch.py:41-50` and `:77-95` stop early only for damaged, blocked, cancelled, disk-full and permission failures. The browser pins carry up to three sources per archive (`src/cadrumo/_data/dependencies/browser_archives.toml`), so this is a regression in behaviour that people will see. No test covers a 404 on the first of two sources (`transfer.rs:821-878` tests a 404 with one source only). Fix: inside the source loop, give way to the next source on every failure except `DamagedDownload`, `BlockedByNetwork`, `DiskFull`, `NoPermission` and cancellation. Keep the last failure, so it is reported after every source has been tried. Add a two-source test for a 404 and for a final resolver failure.

### activity-finish-race | medium | A status read during a writer's finish can read the item as interrupted

`native/application/src/provisioning/activity.rs:92-119` reads `<item>.activity.json` and only then probes the lock. A writer can remove the record and release its lock between those two steps (`ItemWriter::finished` at `activity.rs:165-168` drops the lock after the removal). The read then finds a record and a free lock and returns `Activity::Interrupted`, so a setup that has just completed briefly shows `failed interrupted` with Resume. Fix: take the shared lock first. If it is acquired, read the record while holding it: no writer can start or finish meanwhile, so a record is a genuine interruption and no record is idle. If it is refused, read the record for the running step.

### interrupted-hidden-by-observation | medium | An interruption shows only while the item reads absent

`native/application/src/provisioning/state.rs:296-307` lets the observation decide whenever it is not `Absent`. Two consequences:
- An interrupted update of a usable local AI whose model differs from its pin reads `stale` with Update.
- An interrupted setup whose check reads `failed` or `blocked` shows that category with Try again.

In both cases the person gets a button other than Resume. Constraint 11 of the Rust ADR says a lock held by no live owner, beside an unfinished activity, reads `failed interrupted` and offers Resume. D6 says the next status after an interruption reports `interrupted` with Resume, and D4 binds a Resume click to the unchanged digest so that no second dialog appears. The Update path re-enters the review flow, so that second dialog does appear. Fix: let `Activity::Interrupted` win over `Absent`, `Differs` and `Failed`. Keep `Present` (setup finished but cleanup was cut) and `Unreadable` winning. Alternatively, record the narrower reading as an amendment to constraint 11.

### receipt-timestamp-interop | medium | Receipts written by the Python setup read as unreadable to the Rust engine

`native/application/src/provisioning/receipts.rs:288-300` accepts only the 20-byte form `YYYY-MM-DDTHH:MM:SSZ`, and `receipts.rs:125-129` turns any receipt that fails it into `Unreadable`. The Python setup wrote `verified_at` from `now()` (`src/cadrumo/application/provisioning_browser.py:980`, `src/cadrumo/core/time/clock.py:43`). Pydantic serialises that as `2026-10-24T13:00:00.123456Z` (verified), into the same `components/receipts/<item>.json` path (`src/cadrumo/application/dependency_receipts.py:90`). Once P02 or P03 consults receipts, every installation set up by the Python path reads `unknown`. Its only button, Check again, cannot cure it, and the true state stays hidden. Fix: accept RFC 3339 UTC with optional fractional seconds. Or classify a well-formed legacy receipt as evidence-free absent rather than unreadable, so the files decide.

### withdrawn-full-check-relabelled | medium | The withdrawn Python full check reports quick-check facts as a full verification

`src/cadrumo/application/dependency_withdrawal.py:97-101` always runs the quick check and copies the requested `mode` onto the reading. `dependencies.verify` and a full status therefore return rows marked `full` and `ready` without the headless browser launch, the network preflight or the one-token generation that D7 makes the content of a full check. `aeat config provision verify` thus prints a ready verification that never exercised the item. Fix: keep `mode` as `quick` on a withdrawn reading, or refuse `dependencies.verify` with `not_in_this_build`, until the engine's full check serves it.

### plan-adr-coverage | medium | The plan does not link the accepted environment and single-binary rulings that govern its scope

S03 edits the `CADRUMO_PROXY_*` declarations in `native/application-environment.toml:90-97`, and `native/application/src/provisioning/proxy.rs:14-16` reads those names. Both are governed by the accepted `2026-10-13-canonical-environment-application-internals-adr` (constraint 12; network routing names). P04's `components` role is governed by the accepted `2026-10-17-single-binary-process-tree-adr`. The plan's `related:` links only the Rust and unified-setup ADRs. P01 breaks neither ruling: no password name is declared, and no environment read is wired yet. Fix: link both with `vaultspec-core vault link add` before P04 wires the role's environment profile.

### model-pins-without-generator | medium | The model pin table has no regenerator and no drift or host gate

`src/cadrumo/_data/dependencies/local_ai_models.toml` is hand-maintained. `dev/env/local_ai_pins.py` regenerates and checks only the program table. Nothing re-derives a `manifest_digest` or `download_bytes` from the registry, and nothing checks the table's `hosts` against the declared `model_registry` host group (the browser table has that gate in `dev/env/browser_archive_pins.py`). Constraint 5 keeps regeneration a developer tool under `dev/`. Two pins were confirmed by hand in this review. Fix: extend `just pin-local-ai` to fetch each pinned model's manifest, record the SHA-256 and the layer-plus-config size, and offer `--check` with a declared-host gate.

### retry-first-wait | low | The first retry can wait 1 s, below the contract's 2 s start

`native/application/src/provisioning/transfer.rs:72-82` places each wait in the upper half of the doubling ceiling, so the first retry waits 1 to 2 s and the second 2 to 4 s. D6 says retries start from 2 s, doubling to at most 60 s. Fix: jitter above the base, capped at 60 s. Or record the half-jitter reading in the ADR.

### setup-selection-vs-button | low | The default setup selection includes failures whose row offers no button

`native/application/src/provisioning/state.rs:350-368` selects `failed not_in_this_build` and `failed not_enough_memory` for a default setup, while `state.rs:335-337` gives those rows no recovery action. Exclude them, as the matching blocked reasons are excluded, or give them a button.

### http-unbounded-loops | low | Interim answers and chunk trailers are unbounded in count and ignore cancellation

`native/application/src/provisioning/http.rs:83-116` loops over any number of `1xx` heads, and `http.rs:169-171` over any number of trailer lines. Each line is bounded, but neither loop has a total bound or a cancellation check, so a misbehaving approved host can hold a transfer past Cancel. Bound the interim heads and the trailer bytes.

### browser-pin-source-hosts | low | Browser pin sources are not checked against the table's hosts

`native/application/src/provisioning/pins.rs:135-145` does not require each source's host to be in `hosts`, whereas program pins do (`pins.rs:256-259`). The transfer's hop check still refuses an undeclared host, so this is defence in depth. Add the same check.

### runtime-owner-start-residual | low | The runtime can still start the local AI program for a Python worker

`src/cadrumo_runtime/host/profile_host.py:253` still composes `start_owned_runtime_server`. `src/cadrumo_runtime/adapters/worker_authorization.py:78-85` and `:597-607` admit a `WorkerServerStart` frame under a COMMIT fence of `local-reader.provision` or `dependencies.setup`. Load and verify commits remain admitted, so a worker can still make the Python runtime spawn Ollama, even though no product path sends that frame after c002a7769a. Drop the starter now, or make sure P05.S14 deletes it together with `src/cadrumo/entrypoints/local_reader_operation_composition.py:48-55`.

## Recommendations

- The high finding reopens P01.S02. Re-review only the source loop of `Transfer::fetch` and its new tests after the fix.
- The activity race and the interruption precedence are in-scope fixes to P01.S04 under the existing constraints. If the narrower interruption reading is preferred, the follow-on decision is an amendment to constraint 11 of `2026-10-24-rust-component-provisioning-adr` on which observations an interruption outranks.
- The receipt interoperability fix belongs in P01.S04, or at the latest in P02.S06 before receipts are consulted.
- The relabelled withdrawn full check is a P05.S16 correction.
- Smaller notes:
  - `connection.rs:91` keeps one production `expect`, on a provider configuration that cannot fail.
  - `components/activity` (`items.rs:128`) has no storage-taxonomy category, so storage inventory and reclaim do not see it.
  - The stall tests use 200 ms and 300 ms I/O bounds against servers that never answer. These are deterministic, but they rest on real timeouts rather than signals.
- Verification:
  - Run in this review, with an isolated target directory: `cargo test --lib -- provisioning canonical_json component::` passed 61 tests; `cargo clippy --all-targets` was clean; rustfmt `--check` through stdin was clean; there is no `#[allow]` or `unsafe` in the reviewed Rust.
  - Focused pytest on the touched Python passed 105 of 106. `test_quick_check_on_a_clean_root_answers_every_item_inside_the_bound` failed once under parallel load (2.04 s against its 2 s bound) and passed alone. The ledger records this as the pre-existing cold local AI quick check, so it is not a regression.
  - Reused from the ledger: cargo-deny for S01 and S02, clippy with `--features platform`, `person_operations` tests, ruff, ty, lint-imports and the operation contract manifest.
  - Pending, owned by the Linux desktop dependency evidence owner: the S03 ledger row shows `test_file_contract_json_and_contract_rs_agree[linux-x86-64]` failing on stale digests. They were stale before S01, but S01 and S02 add application `Cargo.toml` and desktop lock drift, so the refresh in `dev/packaging/native/linux_desktop_runtime.py` needs that owner's review.
  - Pre-existing and unrelated: the `package_inspection` junction fixture failure on a non-ASCII path.
