---
tags:
  - '#audit'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-25'
body_schema: 'body-v2'
body_hash: 'sha256:2ad699eee7dfeb632c306d3addd1c7b33c4aea9ccf093b04c9c0755d906391f2'
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

## Scope: plan close

Plan-close review of `2026-10-24-rust-component-provisioning-plan`, all 25 Steps closed.
Base: each commit's parent; target: HEAD `e3b90ac49d`. Reviewed commits, interleaved with
other sessions' unrelated work: `2e68087fba`, `f14f10deda`, `9ad01f48f9` (the P01
corrections), `191520c28d`, `07a0457000`, `25d1f4c659`, `838f35cfba` (P02),
`1ba36937b1`, `868d6ffaab`, `25c2b5448d`, `ec9c027a88` (P03), `b924ce87f9`,
`cb41233c76`, `0295705ba7`, `d54ca8af31`, `7c0f96b7c9`, `08c9311a8f`, `5f796ad4ad`,
`27bb2fef35`, `760b5db808` (P04), `754fbcee5b`, `294736a467`, `f505418cd5`,
`e3b90ac49d` (P05). Uncommitted scope: foreign edits from other sessions in the ledger,
modelo, borrador, locale and desktop-fixture trees; none is this plan's and none was
reviewed.

Every P01 finding of the first round is fixed and re-verified in the current sources:
the source loop gives way on every failure but `DamagedDownload`, `BlockedByNetwork`,
`DiskFull`, `NoPermission` and cancellation (`transfer.rs:181-206`, `:392-401`); the
activity read takes the shared lock before the record and `ItemWriter::finished` removes
the record before the lock drops (`activity.rs:286-316`, `:475-479`); an interruption
now outranks `Absent`, `Differs` and `Failed` and loses only to `Present`, `Unreadable`
and the two blocks (`state.rs:296-313`); receipts accept RFC 3339 UTC with fractional
seconds and a legacy Python receipt is covered (`receipts.rs:489`, `:662-679`); the
default selection is the rows that offer a button (`state.rs:355-363`); jitter sits
above the base (`transfer.rs:85-95`); interim answers and trailers are bounded and ask
the stop (`http.rs:12-17`, `:107`, `:201-207`); model pins regenerate and gate their
hosts (`dev/env/local_ai_model_pins.py`); the withdrawn full check and the runtime's
server-start frame went with `f505418cd5`.

No Python provisions a component. I traced each surface entry to its effect and found no
product Python path that downloads, installs, extracts, verifies, removes, starts the
local AI server or decides a component's state. The `aeat config provision` status,
probe, verify, setup, browser, pull and remove verbs all run `run_components_role`
(`provision_cli.py:350-694`); load and report alone stay registered operations, which
constraint 12 keeps as consumption. The TUI door and screen and the MCP setup tools use
the same client; the desktop links the engine in process; the runtime admits no
server-start frame. `probe_playwright_browser` and `core/component_records.py` only read
the engine's record and test that the paths it names exist. `provisioning_runtime` keeps
load, unload and the inventory read, and no caller asks its endpoint helper for `pull` or
`delete`. The gate's stated blind spots hide nothing today: the only pin readers are
`application/browser_archive_pins.py` and `core/local_ai_pins.py`, whose product callers
are the model catalogue and a packaging coverage tool, and neither imports an HTTP
client; `dev/` is outside the ownership boundary by design and its one remaining
installer use is the shared test browser cache. The one qualification is the doctor row
recorded below, which keeps a parallel Python reading of whether the models are
installed.

## Findings

### retired-command-probe-fixtures | high | Two command probes still name a parameter and a command this plan retired, so both gates fail

`src/cadrumo/entrypoints/cli/tests/test_command_governed_fact_declaration_probe.py:126`
and `src/cadrumo_runtime/host/tests/frontend/cli/test_command_aeat_capability_probe.py:126`
both declare `_HANDLER_REQUIRED_OPTIONS` with `config_provision_remove` requiring
`role`, but P04.S25 replaced that verb's `--role` with a positional `ITEM`, so
`_provision_command_specs.py:195-206` declares only `item` and `yes`. The first file's
own consistency assertion at `:375` therefore fails, reproduced in this review as
`AssertionError: ('config_provision_remove', ('role',))`. In the second file,
`test_the_population_covers_network_commands_and_the_authentication_family` at `:551`
asserts `config_provision_status` is in the AEAT-reaching population, which that verb
left when P04.S12 and P04.S25 made the provision commands profile-free clients of the
components role; reproduced as a bare `AssertionError`. Both are regressions of this
plan, not evidenced pre-existing failures. Fix: drop the `config_provision_remove` entry
from both maps, and replace the `config_provision_status` sentinel with a command that
still declares a network capability, so the population guard keeps catching an empty or
undercounted set.

### engine-config-refusal-category | medium | A refused proxy setting reaches every surface as `unexpected`, and the command line as a protocol error

`native/application/src/provisioning/role_host.rs:127` builds the network with
`ProxySettings::from_settings(text)?`, and `proxy.rs:43-62` deliberately turns a setting
the engine cannot use into `FailureCategory::BlockedByNetwork`. The `?` hands that on as
a plain error, and `protocol.rs:332-341` answers any engine-construction failure with
`outcome: failed`, `failure_category: unexpected` and no rows at all. The command line
then sees an outcome that is not `Ok` on a status and raises
`RefusalError(RefusalCode.INVALID_FRAME)` (`provision_cli.py:350-354`), so a malformed
`CADRUMO_PROXY_URL` prints a broken-protocol refusal instead of the blocked-by-network
sentence constraint 10 and unified-setup D9 give it, and `aeat config check` reports
setup simply unavailable. Fix: carry the construction failure's own category into the
result line, which `Error::Download(failure)` already holds, and keep the status path
answering with its rows.

### manager-proxy-read-once | medium | The server the models are pulled through can bypass the operator's proxy

`native/manager/src/supervision/local_ai.rs:96-98` reads the `CADRUMO_PROXY_*` settings
from the manager's own environment once, inside `for_package`, and discards a refusal
with `.ok().flatten()`. The model bytes are fetched by that server through `/api/pull`,
not by the engine (`native/application/src/provisioning/local_ai/models.rs:344-390`), so
this is the whole proxy path for the local AI. Two consequences follow: a setting the
role refuses as blocked-by-network leaves the server reaching the registry directly, the
opposite of `role_host.rs:127`; and a proxy the operator sets after the manager's login
start stays invisible until the manager restarts, while the role process that plans and
preflights the same setup does see it. Fix: read the settings again each time the
supervisor starts a server, and treat a refused setting as the role treats it rather than
as no proxy at all.

### model-pull-stale-reports-completed | medium | A pull that lands on a manifest other than the pin still reports a completed setup

`native/application/src/provisioning/local_ai/models.rs:185-189` accepts a `Differs`
observation as a successful pull, `state.rs:118-120` counts `Differs` as usable, and
`engine.rs:1373` with `:1379-1384` therefore let the setup run to `writer.finished()`, so
the role answers `completed`. The plan part the person approved named the model and its
pinned manifest digest (`models.rs:108`), so an approval of one model can finish as
another, and the row that follows reads `stale` with Update, whose next pull fetches the
same non-pinned manifest and never converges. The browser's equivalent mismatch is final
at the transfer's digest check. Fix: treat a post-pull `Differs` as a failure of that
part so the outcome names it, or record in constraint 8 of
`2026-10-24-rust-component-provisioning-adr` that a registry tag moved past its pin ends
a setup `completed` with a stale row, and give that row something other than Update.

### components-storage-not-in-taxonomy | medium | The engine's program install and activity folder are invisible to storage inventory and reclaim

`native/application/src/provisioning/items.rs:120-129` puts the local AI program under
`components/ollama/<version>` and the per-item writer locks, activity records and cancel
requests under `components/activity`.
`src/cadrumo/core/storage_taxonomy_locations.py:98-175` declares
`components/ollama/home`, `models/ollama`, `components/playwright` and
`components/receipts`, and neither of those two. `collect_storage_area_inventory` and
`_reclaim_candidates` enumerate the taxonomy alone
(`src/cadrumo/application/storage_management/service.py:115`, `:274-286`), so the
multi-gigabyte program install the ADR's consequences call out is missing from the
reported occupancy and cannot be reclaimed, while the home folder beside it can. Fix:
declare both as root locations, the program with the unbounded-by-design lifecycle and
the dormant reason its siblings carry, the activity folder as fixed-override state.

### doctor-keeps-a-second-model-reading | medium | `aeat config check` shows a parallel Python judgement of whether the local AI's models are installed

`src/cadrumo/application/provisioning.py:1050-1110` still decides a
`local_model_provisioning` row from the server's own model inventory and the `llm` extra,
and `workstation_check.py:130-132` publishes it beside the engine's rows that
`check_cli.py:177` reads from the components role. Its "extra present, no selected model
installed" branch (`:1148-1158`) refuses through `provisioning_no_recovery_verdict`, so
the operator is told the models are missing and given no action, while the reader rows in
the same report carry `operator.provision.local_ai` (`local_reader.py:521-523`) and the
engine's row carries Set up. Constraint 2 leaves the Python surfaces no second state and
constraint 13 wants every refusal of a missing component to name its setup action; the
docstring still describes models an operator pulls into the runtime, the retired world.
Fix: keep only the extra-without-models direction, which is genuinely about the pip
extra, and let the engine's row own the missing-model reading.

### missing-manager-adr-link | medium | The plan does not link the accepted runtime-manager ruling that governs its supervision Steps

P04.S17 and P04.S21 add `native/manager/src/supervision/local_ai.rs` and wire it into the
manager's uninstall, window close, poll, session-end and cancel paths
(`native/manager/src/background.rs:267`, `:298`, `:502`, `:543`, `:577-579`). That
supervision lifecycle is governed by the accepted
`2026-10-04-runtime-manager-architecture-adr`: session-end restart suppression,
containment of owned processes, and supervision of the managed default root only. The
plan's `related:` lists the Rust, unified-setup, canonical-environment and single-binary
records only. The work breaks none of those constraints, which is why this is medium: I
traced `stop_local_ai` through every one of those sites and found a resume only in
`cancel_session_end`, so restarts stay suppressed once session end is observed. Fix:
`vaultspec-core vault link add` the manager ADR to the plan.

### dead-component-symbols | low | Three public symbols of the new surface have no production reader

`src/cadrumo/adapters/outbound/components/client.py:287` exports
`components_role_available`, used only by its own test;
`src/cadrumo/application/local_reader.py:356` exports `configured_role_model`, used only
by tests and test support after P03.S09 moved the readers onto the record; and
`src/cadrumo/core/component_records.py:64` defines `COMPONENT_RECORD_VERSION`, which
nothing reads, because the shape's version is actually enforced by
`receipt_version: Literal[1]` at `:181`. Remove the three, or give the constant the
literal's job so the version is named once.

### contract-mismatch-error-outside-the-hierarchy | low | The client's contract-mismatch signal derives from bare `Exception`

`src/cadrumo/adapters/outbound/components/protocol.py:457` declares
`ComponentsContractMismatchError(Exception)`, the only such class in the product trees,
against the convention that every refusal descends from `CadrumoError`
(`src/cadrumo/core/errors/hierarchy.py:150`). It never escapes `run_components_role`,
which catches it at `client.py:504`, so it is an internal control signal rather than an
operator-facing refusal; naming it as one, or basing it on the hierarchy, would settle
which it is.

### stale-generated-cli-tree | low | The committed help projection still lists the retired `config provision start`

`docs/_static/cli-tree.json:15725` carries an `aeat config provision start` entry that
P04.S25 retired with no alias. The file is generated by `dev/docs/cli_tree.py` and
regenerates on a documentation build that is not told to skip it
(`dev/docs/sequence_build_gate.py:37-59`), so the stale copy corrects itself; until then a
build in skip mode offers the help widget a command path that no longer exists.

### frontend-keeps-the-retired-last-pull-field | low | The desktop ledger type and its dev fixture still carry a field the result dropped

`native/desktop/frontend/src/shell/ledger.ts:1750` declares an optional `last_pull`, and
`native/desktop/frontend/src/dev/ledgerEvidenceFixture.ts:1445` and `:1490` still supply
it, while P05.S14 removed the field from `local-reader.status` and
`ledger.evidence.reader-readiness` in place. Optional, so nothing breaks; but the fixture
no longer matches an envelope the real host can produce, which is what a dev fixture is
for.

## Recommendations: plan close

- The high finding reopens P04.S25, whose parameter change left both probe fixtures
  behind. Both fixes are one line each and need no new scope.
- The refusal category, the manager's proxy read and the stale-pull outcome are in-scope
  corrections under the existing constraints. The stale-pull one carries a follow-on
  decision for the orchestrator to name rather than make: whether constraint 8 of
  `2026-10-24-rust-component-provisioning-adr` means a moved registry tag ends a setup
  `completed`, or whether that part fails.
- The storage-taxonomy omission is a correction to P03.S07's location choices, governed by
  unified-setup D12; declaring the two members changes no engine path.
- The doctor row is the one place a second Python reading of a component survives. If it
  is to stay as the pip-extra coherence check it describes, the models half should go; if
  it is to report missing models, it should read the engine's row. That choice is a
  follow-on decision, not a fix.
- Smaller notes:
  - `role_host.rs:129-131` accepts the declared local AI address without the loopback
    filter the manager applies at `supervision/local_ai.rs:53-58`; the generator and the
    Python reader both refuse a non-loopback value, so this is only the missing third
    check.
  - `core/component_records.py:374-386` reads the local AI record twice, once through
    `locate_component` and again for its facts.
  - The executor's note that the TUI setup screen imports the outbound components adapter
    directly is not a finding: the layering contract places `entrypoints` above
    `adapters`, `lint-imports` keeps all 30 contracts, and the CLI's own
    `provision_cli.py:61` does the same.
- Verification:
  - Run in this review: `cargo test --offline --lib provisioning::` on `native/application`
    with its own target directory, 128 passed; `cargo test --offline --features test-support
    --test provisioning_faults`, 3 passed (the full-disk case is Linux-only);
    `uv run --no-sync lint-imports --config .importlinter --no-cache`, 30 kept 0 broken;
    `pytest dev/quality/tests/test_no_python_provisioning.py
    dev/runtime_lifecycle/tests/test_components_surface_conformance.py
    dev/smoke/tests/test_acquisition_lane.py -m 'not external_tool'`, 21 passed;
    `pytest src/cadrumo/adapters/outbound/components/tests
    src/cadrumo/core/tests/test_component_records.py
    src/cadrumo/entrypoints/cli/tests/test_provision_components_role.py
    src/cadrumo/entrypoints/cli/tests/test_provision_offline_status.py`, 135 passed.
  - Run to confirm the high finding: the two probe assertions named above, each failing on
    this tree.
  - Reused from the ledger: the per-Step cargo, clippy, rustfmt, cargo-deny, ruff, ty,
    operation-contract-manifest and locale runs, the WSL Linux provisioning lane, the
    real-role lane through `just test-components-role`, and the independent plan-digest
    oracle.
  - Checked and met: the plan's quick-check bound is asserted through the real role, with
    this computer's own hardware measured, at
    `native/application/src/provisioning/protocol/tests.rs:1169-1177`.
  - Remaining gaps, each already reported and no worse than stated: macOS paths are
    uncompiled; the Linux desktop dependency evidence digests are stale; the CI fleet owns
    running `just test-native-provisioning-linux`; the `external_tool` cases need a built
    role image and did not run here; the vanilla-machine acquisition run stays pending.

## Scope: plan-close corrections re-review

Re-review of the 2026-10-25 corrections to the plan-close round above. Base: each commit's
parent; target: HEAD `2d9c1e9d20`. Reviewed commits: `673a909899`, `6cdd9770f9`,
`2d9c1e9d20`, `326a031dc1`, `0a45be79d9`, `af038fc92b`, `569cbee45c`, with the coverage
fix `49d8ce4ef3`. Only the changed behaviour and its interactions were read. Uncommitted
scope: foreign edits from other sessions in the borrador, modelo, inventory, locale,
desktop-fixture and vault trees; none is this plan's and none was reviewed.

Disposition of the plan-close findings:

- `retired-command-probe-fixtures` (high): resolved. Both maps are empty and the
  population sentinel is `config_provision_verify`, which still declares the capability;
  46 cases of `test_command_governed_fact_declaration_probe.py` and the population guard
  pass here. One residual note: with both `_HANDLER_REQUIRED_OPTIONS` maps empty, the
  guard loop at `test_command_aeat_capability_probe.py:554-555` now asserts nothing.
- `engine-config-refusal-category` (medium): partly. The role and the desktop setup path
  carry the construction failure's own category (`protocol.rs:332-343`,
  `setup/components.rs:570-583`), and the command line words it and keeps exit 2 on
  `verify`. The TUI, the MCP and the desktop's check path do not; see below.
- `manager-proxy-read-once` (medium): partly. A refused setting no longer leaves the
  server reaching the registry directly (`ServerState::ProxyRefused`,
  `supervision.rs:168-177`), and the engine refuses rather than pulling through a server
  started under another setting. The staleness half does not hold; see below.
- `model-pull-stale-reports-completed` (medium): resolved. `models.rs:185-192` fails the
  part with the integrity category, `engine.rs:1369-1377` therefore never reaches
  `writer.finished()`, and the real-role test asserts `failed`, `damaged_download`, a
  `failed` row and exactly one pull. The row a later quick status derives is noted below.
- `components-storage-not-in-taxonomy` (medium): resolved. Both locations are declared as
  root members with `UNBOUNDED_BY_DESIGN` and `STATE` grouping, so `_reclaim_candidates`
  excludes them twice over (`service.py:277-286` and `RECLAIMABLE_LIFECYCLES` at
  `service.py:70-76`) and a `STATE` reclaim refuses the area outright; they also join the
  protected-descendant members. `components/ollama` is the outermost declaration, so
  `_minimal_paths` (`service.py:492-497`) counts the nested `components/ollama/home` once.
  The two new `StorageCategory` members reach no registered operation schema: the contract
  manifest carries no storage category and its `--check` is clean.
- `doctor-keeps-a-second-model-reading` (medium): resolved. With the extra present the row
  answers available and reads no inventory (`provisioning.py:1086-1091`), so the engine's
  row is the only reading of whether a model is installed; the reader rows that remain are
  the fitness probes constraint 8 keeps in Python. The removed condition id has no other
  reference, and `LOCAL_MODEL_INVENTORY_READABLE` still serves
  `provisioning_runtime.py:672`. Note: with the extra absent the row reads the inventory a
  second time, after `workstation_check.py:115` already read one.
- `missing-manager-adr-link` (medium): resolved by `49d8ce4ef3`; the plan's `related:` now
  lists `2026-10-04-runtime-manager-architecture-adr`.
- `dead-component-symbols` (low): partly. `components_role_available` and
  `COMPONENT_RECORD_VERSION` are gone; `configured_role_model`
  (`src/cadrumo/application/local_reader.py:356`) remains with only test and test-support
  callers.
- `contract-mismatch-error-outside-the-hierarchy` (low): resolved.
  `ComponentsContractMismatchError` descends from `CadrumoError`, is registered as
  `INTERNAL_COMPONENTS_CONTRACT_MISMATCH` and has a sentence in four languages; the
  zero-argument raise at `protocol.py:497` is supported by `CadrumoError.__init__`, and
  `client.py:498` still catches it before it reaches an operator.
- `frontend-keeps-the-retired-last-pull-field` (low): resolved; no `last_pull` remains in
  the desktop type or its fixture.
- `stale-generated-cli-tree` (low): unchanged, as recorded; it regenerates on a
  documentation build.

The owner's requirement still holds after these commits. Nothing added a Python decision
about a component: the categorised refusal only words a category the engine chose, the
taxonomy declaration is a storage statement with no reader or writer, and the doctor's
change removes a reading rather than adding one. The proxy work moves one comparison into
the engine and the manager's supervisor, both Rust.

## Findings: plan-close corrections

### proxy-setting-staleness | medium | The supervisor re-reads an environment that cannot change, so a proxy set after its start still never reaches the server

`native/application/src/provisioning/local_ai/supervision.rs:168-177` and `:234-240` read
the setting at every look through `self.environment`, which the manager supplies as
`std::env::var_os` of its own process
(`native/manager/src/supervision/local_ai.rs:93-100`). A process's environment block is
private and cannot be changed from outside it, and nothing re-applies one here:
`native/platform/src/launch.rs:547` runs once at a packaged image's entry, and
`native/application-environment.toml` declares no manager or desktop profile at all, so
the manager's `CADRUMO_PROXY_*` values stay exactly what its login start inherited, for its
whole life. The new test proves the re-read with an injected mutable closure
(`supervision/tests.rs:239-290`), a shape production cannot produce. Two consequences: the
comment's and the commit's claim that a correction takes effect without a restart is not
true of the only environment the manager has; and where the engine's own process carries a
proxy the manager does not, every local AI setup now bounces the shared server through the
program-change channel and then refuses `blocked_by_network` (`engine.rs:1443-1470`), whose
Try again cannot converge and whose sentence says nothing about the manager that must be
restarted. Fix: read the setting from a source that can change between looks, such as the
canonical declaration on disk or a request to the manager, or keep the refusal and give the
mismatch a notice that names the restart; either way drop the claim at
`supervision.rs:168-170`.

### categorised-refusal-not-on-every-surface | medium | The TUI, the MCP and the desktop check still answer a refused setting as a broken exchange

The role now answers a refused setting with `failed`, its category and no rows, which the
new fixture
`src/cadrumo/tests/fixtures/components_role/status_refused_blocked_by_network.jsonl`
records. Three of the surfaces constraint 2 names do not word it:
`src/cadrumo/entrypoints/tui/setup/door.py:95-97` raises `RefusalError(INVALID_FRAME)` for
any outcome that is not `OK`, including a categorised one, and so does
`src/cadrumo_mcp/mcp/component_setup.py:250-255` for `status` and `verify`;
`native/desktop/src-tauri/src/shell/setup/components.rs:311-333` collapses the same
construction failure into `CheckStage::Failed`, which carries no category at all
(`setup/wire.rs:194-198`). A malformed `CADRUMO_PROXY_URL` therefore still prints a
protocol refusal in the TUI and the MCP and shows a bare failed check in the window, while
the command line prints the blocked-by-network sentence. Fix: keep a categorised result in
`door.py` and `component_setup.py` as `provision_cli.py:350-360` keeps it, wording the
category beneath the rows it has, and give the window check stage the category channel its
setup track already has.

### stale-row-after-a-pin-mismatch | low | A later quick status still offers Update for a model whose registry tag moved

`native/application/src/provisioning/state.rs:296-313` lets `Differs` outrank the recorded
failure, so the setup's own result row reads `failed damaged_download` with Try again, but
the next quick status reads `stale` with Update, whose pull fetches the same non-pinned
manifest and fails again after the whole transfer. `derive_row` already receives
`last_failure`; letting it word a `Differs` whose last setup failed on integrity, or naming
the stale reason in the row, would stop the person paying for the same pull twice.

### proxy-digest-is-an-unsalted-hash-of-a-credential | low | The persisted fingerprint commits to the proxy password outside custody

`native/application/src/provisioning/proxy.rs:104-117` digests host, port, user name,
password and bypass with a plain `Sha256Digest::of`, and `local_ai/program.rs:875-895`
writes that hex into the `server.json` beside the program, an installation-wide file
outside encrypted custody. Nothing logs it and no Python or external consumer reads the
file, so this is not a disclosure; it is a cheap offline check of a guessed weak proxy
password for anyone who can read that root. Either drop the password from the material, so
a changed credential is handled by the restart the setting already needs and the digest
commits to no secret, or record in constraint 10 that a digest over the whole setting is
persisted there and why its location is acceptable.

### program-change-lease-reused-for-a-restart | low | The program lock documented meaning no longer covers its use

`native/application/src/provisioning/local_ai/lease.rs:9-20` describes
`local_ai.program.lock` as an engine right to replace or remove the program, and the
supervisor stops its server when it sees the request. `engine.rs:1455-1462` now takes that
lease to bounce a server whose proxy differs, replacing nothing, and pays up to
`PROGRAM_CHANGE_BUDGET` (60 s) plus a server stop on every such attempt, which the Python
readers see as the server going away. Widen the module stated contract to the restart it
now also serves, or add a named restart request beside it.

### status-exits-zero-on-a-refused-check | low | The provision status command exits 0 when the engine refused the check and reported no item

`src/cadrumo/entrypoints/cli/config/provision_cli.py:368-381` and `:612-625` word the
category, report `complete: false` and no item, and exit 0, which
`test_provision_components_role.py:127-136` fixes as the contract, while `verify` exits 2
and `aeat config check` refuses `UNAVAILABLE`. A reading command exiting 0 is the CLI
convention, but a scripted caller cannot tell a computer with nothing set up from a check
that could not be read by the exit code alone; the JSON envelope `failure_category` is the
only discriminator.

## Recommendations: plan-close corrections

- No critical and no high finding: no Step reopens on this round. Both mediums are
  in-scope corrections under the existing constraints: the surface wording belongs with
  the client Steps of P04, and the proxy reading with P04.S17.
- The proxy setting source carries a follow-on decision for the orchestrator to name
  rather than make: whether the manager supervision reads `CADRUMO_PROXY_*` from its own
  inherited environment, in which case the 2026-10-24 amendment of
  `2026-10-24-rust-component-provisioning-adr` should say that a setting changed after the
  manager start takes effect at its next start and that the engine mismatch refusal is the
  intended outcome, or whether it reads a source that can change, which is a new
  declaration.
- The unsalted fingerprint is the second decision worth naming: constraint 10 says the
  address is a credential and is never logged, and says nothing about a persisted
  derivative of it.
- Smaller notes:
  - The server record schema 1 to 2 move reads safely: a record from an earlier build
    fails the filter in `ServerRecord::read`, so the engine sees no server, while
    `try_serve` still refuses for as long as an earlier manager holds the server lock; a
    start overwrites the file and a stop removes it.
  - `components/activity` is declared fixed, while `components/ollama/home` beside it keeps
    its `cadrumo_ollama_home_dir` override; with the home relocated the two paths are
    measured separately, which is correct but no longer the counted-once case the new
    declaration comment describes.
- Verification:
  - Run in this review, with an isolated target directory: `cargo test --offline --lib
    provisioning::` on `native/application`, 132 passed, plus the four new tests re-run by
    name; `cargo test --offline --features test-support --test provisioning_faults`, 3
    passed; `uv run --no-sync lint-imports --config .importlinter --no-cache`, 30 kept 0
    broken; `python -m dev.operation_contract_manifest.generate --check`, OK; `pytest -q -p
    no:cacheprovider` over `test_provision_components_role.py`, both command probes,
    `test_provisioning_model_inventory.py`, the components adapter tests and the storage
    management tests, 235 passed; `pytest` over `test_storage_liveness_gate.py` and
    `test_retention_wiring_gate.py`, 20 passed.
  - Reused from the ledger: the S17 `cargo test --offline --lib supervision::` on
    `native/manager` and the clippy runs on both crates, the S08 cargo and clippy runs, and
    the S14 and S25 pytest and locale runs.
  - Pending, environment rather than defect: the manager crate does not compile in this
    session, because `cadrumo-platform` includes the contract that `CADRUMO_CONTRACT_RS`
    names and only the CMake `native_contract` target generates it; the desktop crate edit
    is likewise uncompiled, as its gate needs CMake. Both rest on the ledger evidence
    above, and the desktop source reads consistently: the added `browser::failure_category`
    is public and `failure()` maps every closed category.
  - Environment gaps in the pytest run, neither a defect of these commits: 7 cases of
    `adapters/outbound/components/tests/test_client_drives_the_real_role.py` fail at setup
    for want of a built role image in `CADRUMO_DEVELOPMENT_ROLE_IMAGE`; 16
    `test_the_instrument_fires_on_a_command_that_declares_aeat` cases refuse
    `browser_not_provisioned` because the shared browser cache of this host
    (`components/playwright` under its storage root) is empty, so the root conftest
    registers no engine record for it. A host with the provisioned cache is needed to clear
    the second set; the refusal is the contract constraint 6 asks for, not a regression.
