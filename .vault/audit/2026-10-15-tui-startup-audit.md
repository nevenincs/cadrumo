---
tags:
  - '#audit'
  - '#tui-startup'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:5bbdd2bd87bf9fa89e86bf5525122d4bb2d1614e469f2ed8cc25cb8181b67dde'
related:
  - '[[2026-10-15-tui-startup-plan]]'
---
# `tui-startup` audit: setup-first startup and private agent identity

## Scope

Integrated review of the working-tree implementation against baseline `86ac35ae43`, plan `2026-10-15-tui-startup-plan`, and the accepted incomplete-profile amendment to `2026-09-02-unreachable-capability-tui-navigation-join-adr`. Reviewed Python startup composition, root navigation and retirement, profile identity checks, lazy workbench loading, and native agent identity observation. Concurrent session-activity, runtime, profile-wizard, packaging and documentation changes remain separately owned. No rebuilt installed-package timing is claimed.

## Findings

### setup-first | low | Incomplete profiles now reach setup before operational capture

`src/cadrumo/entrypoints/tui/runtime_initial_root.py` reads an authenticated exact-profile overview and non-touching session status. Explicit INCOMPLETE state selects the existing profile manager, with other destinations never captured. Empty missing-field counts cannot implicitly complete setup. Complete profiles take the existing full workbench path. Closing setup loads the full root and publishes its matching Home, catalogue, account and search presentation together. The same client and retirement, session observation and concurrent activity reporting remain bound. No extra login or local custody is introduced. Review traced delayed factory identity checks, cancellation-complete root loading, stale-result suppression and root teardown. A complete profile pays an additional profile overview for routing; the subsequent full root intentionally rereads authoritative data.

### import-cost | low | Login no longer imports the operational workbench

Annotation-only screen imports moved under TYPE_CHECKING. Installed human-session composition locally imports the initial root after admission. Fresh-process coverage verifies the full workbench module is absent. Source module count fell from 2411 to 1158. One before/after source sample was 6426.1565 ms versus 1337.698 ms; later samples under concurrent builds ranged 3196.098–6746.600 ms. These are import measurements, not end-to-end launch benchmarks, and cannot establish a reliable speedup percentage. Debug diagnostics now distinguish initial profile read, deferred workbench load, and first rendered destination.

### agent-identity | low | The machine observation uses the existing scoped opaque-ID opt-in

`native/desktop/src-tauri/src/shell/sign_in/mod.rs` uses a dedicated private status call with `CADRUMO_CLI_REVEAL_IDENTIFIERS=1` on that child command only. The exact selected label and canonical UUID remain mandatory. Ordinary status/login/list/create/logout calls preserve inherited privacy behavior. Tests reject both a foreign label and the redacted placeholder; default Python JSON rendering still redacts opaque IDs and preserves taxpayer-data redaction under the opt-in.

### verification | low | Focused behavior passes; shared repository verification remains pending

The 60-test TUI/root/installed-session suite passed, plus four explicit-state/foreign-profile routing cases. The real native password/API/password recomposition test passed in 40.18 seconds on retry, proving no generation before either wizard and generation on Home return. The earlier attempt timed out at observer login before the TUI launched. Canonical JSON identifier-redaction coverage passed. Desktop CMake unit tests filtered to `shell::sign_in::` passed 57 tests, including both new identity tests; the previous cache filter `logs::` had run a different 57-test set and is not counted as identity coverage. Native lint is still running. Focused Ruff and ty checks pass. Registry gate passed. The broader code gate failed during concurrent source mutations (an unrelated syntax error, repository-only test import, private-boundary findings, and stale import metadata). Import metadata was subsequently regenerated to enroll the new loader and other concurrently added modules. The full test gate is still running. Whole-package host checks twice refused changing documentation inputs; the supported backend unit targets provided focused native coverage.

### measured-remainder | medium | Profile overview pagination still delays the first wizard

The passing native retry recorded first and second initial profile reads of 7.938683 and 6.046712 seconds; first rendered wizard timings were 8.320677 and 6.636174 seconds from root construction. Password admission itself took 0.486705 and 0.479709 seconds. Each overview required seven sequential durable `user-profile.view` operations. Their settlement timestamps span 5.102 and 4.949 seconds; these are spans, not per-call durations. Deferred Home took 11.815532 seconds, including generation and a fresh seven-page overview. The test is a synthetic source-worktree native IPC journey under shared load, not packaged launch evidence. `frontend_profile_view_client.py` already requests the maximum 32 items; `view_operation.py` caps serialized results at 20,000 bytes beneath the runtime frame limit. Each page reloads and validates the record and rebuilds the overview in `view_reader.py`. There is no existing larger-page caller option or retained snapshot to reuse. Changing that protocol needs separate measured work preserving byte bounds, revision/digest pinning and refusal of partial collections.

### native-verification | low | Identity regressions and backend lint pass

The supported CMake `desktop-host-unit-test` target with filter `shell::sign_in::` passed 57 tests, explicitly including the private identity environment and exact-profile UUID tests. `desktop-host-unit-clippy` passed. The pre-existing local test filter `logs::` was restored. A subsequent rustfmt check found formatting in concurrently edited `wire.rs`; the startup identity module itself matched rustfmt. The first-screen timing events were observed in the passing native test's product log.

### complete-profile-follow-up | low | Revalidate the routing capture instead of reading the complete overview twice

Follow-up review removed the duplicate full overview noted above for complete-profile startup. `RuntimeWorkbenchRoot.load(initial_profile=...)` now rereads the canonical STATUS stream after generation; it reuses the routing overview only when exact profile ID, record revision, content digest and explicit setup state match. Any difference triggers the full fresh overview read. Later Home refreshes never reuse the routing capture. This preserves currentness without a new cache or protocol. All nine routing/provenance tests pass, including each changed provenance field; focused Ruff and ty pass. Concurrent profile-client renames were preserved (`profile/overview_client.py`, `read_profile_overview`). Final native workbench regression verification is in progress.

### final-verification | low | Focused implementation passes; integrated release status remains PENDING

Final current-source run: 69 TUI routing/root/app/installed-session tests passed in 62.30 seconds (`.tmp/startup-audit-20261015/focused-final.txt`). All three real native workbench tests passed in 255.24 seconds (`native-workbench-final.txt`), covering secure generation, exact-profile/API admission restrictions and the launcher wizard-to-Home journey. Seven regenerated import-inventory tests passed. The broad test gate was stopped deliberately after 8,682 passes, 380 failures and 163 started tests without recorded results; serial and harness stages were not reached. Its failures span operation-contract parity, storage/access-policy/CLI and other concurrent work. The one reported TUI abandonment case passed alone on the current tree (`acceptance-rerun.txt`). This partial run is not complete coverage. Code-gate failures and ongoing shared changes preclude a clean integrated verdict. No package was rebuilt or installed, and mixed-owner source files were not committed as startup-only work. Plan Steps remain open pending integrated verification and a safe shared-file commit boundary.

### overview-page-budget | low | Seven reads reduced to five within existing byte bounds

User-authorized S03 raises the profile-view item cap from 32 to 128; the unchanged 20,000-byte ceiling now determines normal overview page boundaries. A synthetic empty incomplete profile has 203 display items: seven old pages become five (44, 35, 46, 46, 32 items; 19,636, 19,941, 19,471, 19,979, 13,769 serialized bytes). Three alternating direct-reader runs measured medians 273.39 ms before and 196.56 ms after; these exclude native IPC and are not launch timings. Regression coverage compares exact items, revision/digest, final reconstructed overview and per-page bytes. Existing stale-pin and oversized-item refusal checks pass. Sixteen focused profile/manifest tests and one real Windows CLI/TUI stream integration test pass; scoped Ruff, formatting, ty and manifest freshness pass. Evidence: `.tmp/startup-audit-20261015/profile-page-fix-tests.txt` and `profile-page-fix-native.txt`. Generated manifest changes are confined to the profile-view request contract and aggregate digest. No new cache or authority path. Integrated release review remains PENDING for previously recorded gate gaps; the staged application has not been rebuilt.
## Recommendations

Keep the plan open until outstanding verification is resolved. Preserve the successful focused results while inputs remain unchanged. Rebuild and measure the user's staged package before claiming its double-click-to-wizard latency. Treat first-screen timings as UI readiness evidence and handoff timings as authentication evidence; neither substitutes for the other.

