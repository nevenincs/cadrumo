---
tags:
  - '#audit'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:106b4185625be0ae9935b55528492d29339a52e30bbd5e7fdbcfcdb92d2f8d76'
related:
  - "[[2026-10-04-desktop-shell-plan]]"
  - "[[2026-10-04-canonical-environment-plan]]"
---

# `desktop-shell` audit: `desktop-shell committed work review`

## Scope

Independent read-only review on 2026-10-05 of committed desktop-shell work (S01 docs and delegated-inventory parts of a87038dd6d, d12e3e06b2, 233a8c2e33; S02 a18b028b54; S03 5aabe8be7e; S08 da945b366f and 10066c1c71; S18 89fe544a85 and a7b9e8e891) and canonical-environment S01 c4214c73a9 with its projection 00f44b5ae1, against the accepted desktop-shell, canonical-environment, interpreter-foundation, distribution, runtime-manager and sign-in decisions. Uncommitted S04 to S07 and another writer's in-flight storage-vector move were excluded. Verdict: revision required. S08 fails on one high boundary finding; S01, S02, S03 and canonical-environment S01 and S02 pass with findings; S18 passes.

## Findings

### contract-step-ids | high | contract.ts names plan Step identifiers in shipped frontend source

`native/desktop/frontend/src/ipc/contract.ts` introduced in da945b366f labels types with plan Step identifiers and fences the terminal block with Step-named markers, which the rule that code stands alone forbids. Comments must describe behavior, for example that a command is not yet served or that a field is present only when the page lists the feature. Reopens S08.

### relocated-root-test | medium | S02 relocated-layout test asserts the working-directory default that canonical-environment rejects

`native/desktop/src-tauri/src/terminal/tests.rs:289-291,361` at a18b028b54, carried into the uncommitted `terminal/tests/live.rs`, asserts that installed mode anchors at the launch directory and that an unpinned child nests. It passes only because `native/platform/src/lib.rs` still walks the working directory, and fails once canonical-environment S03 lands. The tui-kind block asserts nothing directly.

### product-allowlist-development-root | medium | the product allowlist projects the development-only root variable into installed packages

`src/cadrumo/core/storage_environment.py:505` builds the product allowlist from both root variables, so the generated contract lets the installed host pass the development variable to children, contrary to the accepted decision's statement that it is not projected into installed packages. The decision's wording is itself inconsistent between two passages.

### import-load-targets-stale | medium | committed import-load targets omit the new dev modules

At a7b9e8e891 `dev/quality/metadata/import_load_targets.dev.json` lacks `dev.docs.desktop_palette`, `dev.locales.desktop_chrome` and the three new `dev.packaging.native` docs and inventory modules, so the collectability gate fails at HEAD.

### docs-build-root-literal | medium | docs_build.py spells the storage root variable literally

`dev/packaging/native/docs_build.py:39` writes the root variable name as a literal inside the canonical-environment literal-gate scope; it predates the decision's acceptance. `native/cmake/Packaging.cmake:64,71` test environments carry the same literal and belong to the packaging owner.

### json-array-token | low | committed contract and dispatcher disagree on a JSON byte-array body

contract.ts says a byte-array body carries the token in the header, while `app.rs:52` at a18b028b54 reads only the argument from any JSON body. No committed command uses that path; the uncommitted dispatcher change fixes it and needs a test landing with it.

### remote-gate-coverage | low | the remote-reference gate checks HTML attributes only

`dev/packaging/native/docs_stage.py:64-75,129-148` does not scan staged CSS url() and import rules, inline style attributes, refresh meta, form actions or imagesrcset.

### inventory-path-parity | low | three inventory readers validate member paths differently

Python and Rust agree; `native/interpreter/bootstrap.py:45-49` lacks reserved-name, trailing-dot and control-character refusals, and no shared vectors prove parity.

### web-flavor-identity | low | the web flavor byte-identity verification was narrowed to the script list

`dev/docs/tests/test_docs_desktop_flavor.py:211` compares script sources only, not the fixture page the plan named.

### temporary-files-spelling | low | the declaration module spells the temporary-files location twice

`src/cadrumo/core/storage_environment.py:491` spells the variable and subpath while `child_environment` reads the taxonomy member.

### pending-verification | low | end-to-end proof remains pending and is not a code defect

Pending: the full four-language docs build and rebuild behavior, the Release docs bundle and the shell frame-src change (S01); the adversarial docs-frame isolation proof (S10, no interactive session in Session 0); a re-run of S02 live tests on a current package; Rust replay of the conformance vectors (canonical-environment S03) and the literal gate (S05); confirmation that Windows profile workers receive non-secret settings through the operation request.

### localized-term-records | medium | localized docs search returns Spanish-key term titles and domain crumbs

Observed by the designer session on 2026-10-05 against the 2026-10-04 Catalan web-flavor build with the current bridge: term results carry unaccented lowercase Spanish keys as titles (for example "regimen del recargo de equivalencia") and Spanish domain words in the crumb, taken from Pagefind record meta read at `docs/_static/cadrumo-docs.js:554-571` and produced by the record injection in `dev/docs/pagefind_inject.py` and `dev/docs/terminology/concept_card_projection.py`. Needs confirmation on a fresh desktop-flavor build, currently blocked by the stale authority; if confirmed, the localized term records should carry the localized display title and domain label rather than the canonical key.

### second-review | low | second independent review of S04 to S08, S11, S14, S15 and S19 found no critical or high defects

Read-only review on 2026-10-05 of ce3adf79e8, 97e941334d, ca1936819a, f0d5414dd7, d0649ebbb4, 9c4c240ace and the follow-ups through 5ce4452635. Prior findings contract-step-ids, relocated-root-test, import-load-targets-stale, docs-build-root-literal and remote-gate-coverage are fixed. Sound: the single token check over every command and body form, postMessage-fallback responses bypassing the fetch queue, context-menu sentinel ordering, docs-scheme containment with CSP on every response, the unsafe blocks and DACL in the platform desktop module, atomic window state, and the log view excluding captured output.

### contract-section-split | medium | the single-instance section splits the native distribution paragraph mid-sentence

`native/CONTRACT.md:784-786` and `:849` at 5878a051b1: the section was inserted after the word "The" of the distribution identity sentence, which resumes under the wrong heading.

### logs-ui-thread | medium | log commands run on the main thread and wait on a lock held across file I/O

`native/desktop/src-tauri/src/logs/mod.rs:79-95,126-134,153-158`: synchronous subscribe and unsubscribe run on the UI thread while the tick holds the hub mutex across up to 16 MiB of reads, so a large log stalls the window at startup and reload; `open_external` also runs ShellExecute on the UI thread.

### log-batch-bytes | low | log batches are bounded by record count, not size

`logs/record.rs:16` with `tail.rs:27,29` and `shell/channel.rs:40-49`: one batch can become a single eval script of tens of megabytes.

### log-idle-polling | low | the log tail reopens every rotation every 100 ms without a subscriber

`logs/mod.rs:109-117` and `tail.rs:313-326,517-535`.

### interceptor-failure-invisible | low | the channel interceptor reports every frame as delivered

`shell/channel.rs:19-27` always succeeds, so terminal and log sinks cannot detect a dead receiver; material only at shutdown with the pinned runtime.

### reload-orphan-session | low | a terminal open racing a shell reload leaves an unowned live session

`terminal/mod.rs:270-276` with `terminal/ipc.rs:72-90`: the new document is refused that kind until the window closes.

### stale-acknowledgement | low | a late activation acknowledgement can satisfy a later claimant

`native/platform/src/desktop.rs:638-645,683-689`: the acknowledgement event is not drained before a new activation.

### global-name-squatting | low | another local account can deny the GUI by squatting predictable Global names

`desktop.rs:468-485,588`: refusal is correct but the names are predictable; the residual denial-of-service risk is unrecorded.

### no-top-navigation-policy | low | nothing prevents the top frame navigating away from the shell

`app.rs:149-154` has no navigation handler; a top-level navigation replaces the shell and settles every session.

### webview2-ambient-overrides | low | ambient WEBVIEW2 variables relocate the profile or open a debugging port

The host inherits `WEBVIEW2_USER_DATA_FOLDER`, `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` and `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`, which take precedence over `app.rs:152`.

### mailto-parameters | low | open_external passes arbitrary mailto headers

`shell/external.rs:43` admits headers such as attach.

### clipboard-read-unbounded | low | clipboard read has no size bound

`shell/clipboard.rs:24-29`.

### contract-timestamp-comment | low | contract.ts misdescribes timestampMs for Python records

`native/desktop/frontend/src/ipc/contract.ts:150` claims parsing; the host always sends null for Python records.

### d2-sign-in-presentation | low | S17 passes presentation review and browser verification

2026-10-05: root reviewed the S17 working-tree change against bcdce3f752, including raw UTF-8 password submission, buffer clearing, typed refusal/countdown, TUI admission presentation, explicit handover, global sign-out and refresh behavior. A review correction invalidates stale status reads at mutation start and suppresses focus reads during mutation; the browser test releases a stale present response after logout and proves it cannot relaunch the TUI. No critical or high finding remains in this scope. npm build and check pass; 17 browser presentation tests and a focused race rerun pass; 16 desktop-chrome locale tests, Ruff and ty pass. These tests run the React shell/Tauri adapter against a transport fixture, not a native sign-in acceptance environment. Build output: `build/d2-desktop`, ports 15370/15371. S17 is complete as a presentation Step; S16/S10 native and packaged verification, S12 manager-start integration and S09 live desktop smoke remain open.

### d1-sign-in-host-checkpoint | low | Windows host checks pass while S16 acceptance remains pending

2026-10-05 review of D1's seven-file S16 change: root inspected package-manifest binary selection, pinned environment, raw secret serialization, zeroized owned buffers, bounded output, CLI envelope translation, central token dispatch and close-time cleanup. Cleanup retains an unsettled child and both sign-in and terminal cleanup are attempted even if one fails. D1 matched all seven source files to the tested snapshot by SHA256. 132 desktop unit tests, including ten sign-in tests and real Windows subprocess EOF/flood/close cases, passed; clippy with warnings denied and formatting passed. Logs: `build/s16-desktop-host/test-all.log`, `test-sign-in.log`, `clippy.log`. The D2 TypeScript shapes agree with Rust serialization.

Verdict PENDING for full S16: the host conservatively reports non-Windows sign-in unsupported until the backend exposes authoritative GNOME observer capability. Actual packaged CLI/UI secret isolation and end-to-end sign-in remain unverified under S16/S10. The runner owns only its direct CLI child; inspected current login/status/logout leaves connect to the existing runtime and do not spawn descendants, but descendant pipe containment is not established. S16 stays open. S12 manager-start integration is separately pending; no dead UI control was added.

### packaged-cli-argument-correction | low | Canonical JSON selection fixed before interactive acceptance

2026-10-05 acceptance preparation found that the S16 host invoked an unsupported leaf `--json` argument. The host now passes the canonical root `--format json` before `config <leaf>`, retaining stdin-only secrets and the verified executable/environment. The earlier unit evidence did not exercise the real CLI parser. The separate WebView2 test host builds successfully from the corrected source; SHA256 `e07fb22ff0bf24d0183d7ac32d20c5ca884787f27e7ed9d03cf3add38a053687`, log `build/windows-x86-64/e2e-desktop/host-build.log`. Full S16/S10 verdict remains PENDING until the current package is driven from an interactive desktop.

### interactive-acceptance-harness | low | Harness corrections verified; product E2E remains pending

2026-10-05 root reviewed the S10 extension across actual CLI profile creation, manually owned contained runtime, production handshake, raw password form, shared status/logout parity, live argv/log/docs isolation and narrow fixture cleanup. No runtime-session override, service or bridge is installed. Setup failures cannot report cleanup PASS. Typed CLI error evidence is bounded and scrubbed. Three real frontend flows now check palette selection against the exact authenticated docs reply, localized Home and appearance handback.

The first final-source harness regression reproduced an EPERM browser-profile teardown failure after 19 assertions passed. Root verified and terminated only that test process tree. The correction closes the browser gracefully, attempts every release even after individual errors and bounds cleanup retries; reviewed rerun passes 20 tests, exit 0 (`build/windows-x86-64/e2e-desktop/harness-tests-reviewed.log`). Formatting, syntax, Ruff and diff checks pass. These are harness/stand-in checks, not product acceptance. S10/S16 remain PENDING for the full package on the interactive desktop; the user has agreed to run the prepared command. Manager-backed S12 also remains pending production manager composition and B4 shutdown/count/schema contracts.

### ledger-prerequisite-contract-fixes | low | Successful changed-ID updates and repeated merge argv corrected

2026-10-05 full documentation prerequisite exposed two current backend defects, independently reproduced with current contracts. Update correlation rejected a successful amount/narrative edit because the resulting content-derived ID differs from the submitted source ID. The result now carries its authoritative resolved source identity; correlation retains source-prefix, profile, result-reference, effect and patch checks, and no-effect results must retain identity. CLI merge now normalizes repeated option values to the strict tuple request. Root reviewed all seven changed files; these paths had no prior external edits. Focused and related suites pass 37 tests including actual command parsing, changed-ID wire roundtrip, mismatched-source refusal and encrypted-repository integration. Ruff, formatting, ty and diff checks pass. Full S10 acceptance remains PENDING: fresh workers/packages and a clean docs gate are still required; this review does not accept other observed golden differences or runtime timeouts.

### selected-profile-signout-acceptance | low | 2026-10-05

Reviewed scoped logout selection correction: successful global human sign-out leaves the non-authoritative selected profile pointer untouched, including concurrent selection. Four integration tests cover same-profile status, concurrent selection, absent proof refusal and corrupt pointer; Ruff and ty pass. Packaged assertions now require the same synthetic profile UUID before and after sign-out. Fixture profile enrollment alone allows 300 seconds for cold calibration and records timings; host production deadlines are unchanged. External B4 changes share custody.py, so that mixed file remains uncommitted. This does not establish actual WebView2 acceptance.

## Recommendations

- contract-step-ids: rewrite the comments behaviorally when S08 adds the terminal types.
- relocated-root-test: derive the expected root from an explicit absolute root or the per-user default and assert the tui exit status.
- product-allowlist-development-root: project only the primary root variable for installed packages, give development its own projection, and reconcile the canonical-environment decision wording.
- import-load-targets-stale and docs-build-root-literal: regenerate and commit the targets; read the variable from the declaration and hand the CMake literals to the packaging owner.
- Low findings: extend the remote gate to CSS and attributes, add shared path vectors replayed by pytest and Rust, either restore the fixture-page comparison or record the narrower claim, read the temporary-files member, and land the dispatcher array test with the S04 to S07 commit.
- Add a test proving app plugins expose no invoke handler beyond the dispatcher, and include Docs.cmake only when docs are packaged or the desktop is configured.
