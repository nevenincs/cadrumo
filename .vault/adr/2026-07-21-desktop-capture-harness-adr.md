---
tags:
  - '#adr'
  - '#desktop-capture-harness'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - '[[2026-07-19-post-release-distribution-adr]]'
  - '[[2026-07-16-distribution-harness-identity-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `desktop-capture-harness` adr: `automated Claude Desktop real-client capture harness` | (**status:** `accepted`)

## Problem Statement

The `claude-desktop-mcpb` and `claude-desktop-plugin` distribution rows are real-Claude-client claims: the honesty guard in `dev/packaging/distribution_evidence_emit.py` refuses an SDK-driven record for them and requires a real client session. The `2026-07-19-post-release-distribution-adr` deferred these rows to an operator-tail of MANUAL in-app captures. The operator has now directed that the capture be an automated test — a proper harness with a reproducible, clean environment every run, with the Claude Desktop application installed — so the manual-capture assumption of that ADR's tail is superseded for the Desktop rows. This ADR records how the automation is achievable on Windows and the decisions that shape it.

## Considerations

- Claude Desktop on Windows is an MSIX / Store FullTrust Electron app (package family `Claude_pzs8sxrjxfjjc`, AppId `Claude`), empirically characterized on 2026-07-21: custom Electron flags reach the app only through Store activation (`IApplicationActivationManager::ActivateApplication`).
- Store activation is DENIED (`E_ACCESSDENIED`) to an elevated Session-0 non-interactive caller; it succeeds from a non-elevated interactive session (verified via a scheduled-task bridge).
- Electron single-instance forwarding: a launch while another Desktop instance runs forwards argv to the primary and exits, silently dropping `--remote-debugging-port`. The harness must own the PRIMARY instance.
- Desktop session auth is the Electron safeStorage `oauth:tokenCacheV2` value in the profile's `config.json`, DPAPI-bound to the WINDOWS USER, not to the profile directory — so it is seedable into a fresh isolated profile by file copy for the same user, mirroring the `.credentials.json` seeding precedent in `dev/packaging/smoke_plugin_install.py`.
- Desktop pipes each MCP server's stderr to `logs/mcp-server-<name>.log` inside the active profile; the cadrumo server's telemetry there carries the typed transport field and attested CLI identity (commit `60d7120e22`), giving a client-side proof of a REAL tool call stronger than model narration.
- Coordinator posture rulings (2026-07-21): captures run against an ISOLATED per-run platform root on the MCP server side too (never the operator's real storage; a default-root launch can hit the retired-aeat-state refusal), and capture success gates on the tool call RESULT succeeding, not merely being dispatched.
- The model may not tool-call on the first prompt; the loop must be bounded-retry, fail-closed with full per-attempt diagnostics.
- Seeded auth material must never persist into retained evidence; the fail-closed leak scan of `smoke_plugin_install` is the required pattern.

## Considered options

1. Keep manual operator in-app captures (the post-release ADR tail). Rejected by operator directive: not reproducible, not clean-environment, does not scale to every release.
2. Drive Desktop with an OS-level UI automation robot (screen coordinates / UIA). Rejected: brittle against UI changes, cannot read renderer state, and offers no stronger proof than CDP.
3. Playwright's Electron launcher. Rejected as the launch mechanism: it spawns the Electron binary itself, which the MSIX activation requirement defeats; Store identity is lost on a direct spawn from an arbitrary context.
4. Launch via MSIX activation with `--remote-debugging-port` + `--user-data-dir`, then attach with CDP (`connect_over_cdp`). Accepted: the app runs with its real Store identity, the profile is per-run isolated, and the drive is deterministic against the renderer DOM.
5. Fallback (designed in advance, used only if the app ignores `--user-data-dir`): direct `CreateProcess` of the WindowsApps executable with a redirected `APPDATA`, pointing all profile state at an isolated root (`launch_desktop_direct_appdata`).

## Constraints

- The launch step MUST execute in a non-elevated interactive user session; the standing elevated Session-0 agent context cannot activate the app and must bridge (scheduled task with `LogonType Interactive`, approved) or delegate to an interactive runner.
- The harness requires exclusive ownership of Desktop for the run window: any running instance is closed GRACEFULLY first (WM_CLOSE via `taskkill` without `/F`; force only after a grace budget), and Desktop is left closed afterward.
- One-time interactive operator login into the blessed source profile is the auth root; the harness only ever reads the curated seed set from it.
- Whether `Claude.exe` honors `--user-data-dir` is not yet empirically confirmed (untestable without primary-instance ownership); the harness aborts BEFORE driving if the isolated profile gains no runtime state after launch, so nothing lands in the real profile, and the APPDATA-redirection fallback takes over.
- Claude Cowork (browser claude.ai) is out of scope for this record beyond assessment; its capture would be a Playwright persistent-auth browser profile, a separate decision.

## Implementation

`dev/packaging/desktop_capture.py` holds the primitives: package discovery (`Get-AppxPackage` parse), running-instance enumeration, curated auth-state seeding (`AUTH_SEED_PATHS`: `config.json`, `Local State`, Chromium cookies/storage — nothing else, so history/caches/other extensions start empty), single-extension provisioning with a rewritten per-run user-config (isolated `storage_root`), MSIX activation with debug flags, CDP readiness polling, the CDP prompt drive, MCP-log telemetry parsing with the result-success gate (`McpToolCall.succeeded`: genuine transport AND no error marker), bounded fail-closed retry, seeded-secret collection, and the artifact leak scan.

`dev/packaging/smoke_desktop_client.py` composes them: run the owned installed-MCP protocol oracle for the rigorous grounded tax proof (the in-app model only proves the real-client dimension with one deterministic single-tool prompt); provision the isolated profile; assert/acquire primary-instance ownership; activate with `--remote-debugging-port` and `--user-data-dir`; abort-before-drive if the isolated profile shows no runtime state; drive with bounded retries gated on a NEW SUCCESSFUL telemetry call; leak-scan every retained artifact; then mint the row via `emit_client_evidence` with the real client identity (`claude-desktop`, the installed package version and executable) and the automated session record. The `just desktop-capture` recipe is the one-command entry point. Harness-logic tests live in `dev/packaging/tests/test_desktop_capture.py` against real files and scripted attempt callables; the launched-app run is the operator/coordinator-dispatched integration surface.

## Rationale

CDP-over-activation is the only launch shape that keeps all four required properties at once: real Store-identity client (the row is a real-client claim), per-run clean profile (operator directive), deterministic scriptable drive (automation directive), and client-side telemetry proof of the served tool call (honesty). The manual tail it supersedes had none of the first three guarantees, and the result-success gate closes the connected-plus-dispatched false-pass the prior smoke session check permitted.

## Consequences

- The Desktop rows become mintable by one command per release instead of a manual in-app ritual; the capture is reproducible and its environment is clean by construction.
- The `2026-07-19-post-release-distribution-adr` operator-tail doctrine is narrowed: for the two Desktop rows the manual capture assumption is superseded by this harness; the Claude Code row and Cowork remain on their existing paths.
- The run requires an interactive-session window with exclusive Desktop ownership; on the operator's workstation that is disruptive and coordinator-authorized per run, and the durable home is a dedicated interactive CI/runner user.
- The single-instance and activation walls are Desktop-version-dependent behavior; a Desktop update that changes them breaks the harness loudly (CDP never answers, or activation fails), never silently — and the abort-before-drive guard keeps the operator's real profile untouched in every failure mode.
- The `--user-data-dir` residual unknown is carried honestly: first real run resolves it, and the pre-designed APPDATA-redirection fallback bounds the blast radius to one aborted launch.
