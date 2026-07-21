---
tags:
  - '#reference'
  - '#desktop-capture-harness'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - '[[2026-07-21-desktop-capture-harness-adr]]'
---

# `desktop-capture-harness` reference: `Claude Desktop MSIX launch, isolation, and auth empirical model`

Empirical grounding gathered on the host `gw-workstation` on 2026-07-21 with non-destructive probes. Every claim below was observed, not assumed; the operator's running Desktop instance was left untouched throughout.

## App identity

- Claude Desktop is a Windows MSIX / Store FullTrust Electron app. `Get-AppxPackage -Name Claude` reports package `Claude_1.22209.3.0_x64__pzs8sxrjxfjjc`, `PackageFamilyName` `Claude_pzs8sxrjxfjjc`.
- Manifest `AppId` is `Claude`; the AppUserModelId is therefore `Claude_pzs8sxrjxfjjc!Claude`. The FullTrust executable is `InstallLocation\app\Claude.exe` under `C:\Program Files\WindowsApps\...`.
- Manifest declares capabilities `runFullTrust`, `unvirtualizedResources`, `localSystemServices`, and a `claude:` URI protocol handler. There is NO AppExecutionAlias (no PATH entry; the `claude` alias on PATH is the unrelated Claude Code CLI).

## State model

- All mutable state lives under `%APPDATA%\Claude` (Roaming, unvirtualized real path, not redirected by Store appdata virtualization).
- Installed MCPB extensions live under `Claude Extensions\<id>\` with an enablement/user-config record at `Claude Extensions Settings\<id>.json`. The cadrumo MCPB is present and enabled as `local.mcpb.cadrumo-project-neve.md.cadrumo`, manifest version `0.2.1`, launch `uv run --no-project --directory ${__dirname} src/server.py`, with `CADRUMO_LOCAL_STORAGE_ROOT`/`CADRUMO_MCP_PERSONA`/`CADRUMO_MCP_SURFACE`/`CADRUMO_MCP_REQUIRED_VERSION`/`CADRUMO_MCP_COHORT_SHA256` env.
- `config.json` holds session auth as `oauth:tokenCacheV2` (and `oauth:tokenCache`), Electron safeStorage ciphertext with a base64 `djEw` (`v10`) prefix. On Windows safeStorage is DPAPI, bound to the WINDOWS USER account, not to the profile directory.
- Chromium session state is under `Network\Cookies`, `Local Storage`, `Session Storage`, and `Local State`.
- Desktop pipes each MCP server's stderr to `logs\mcp-server-<name>.log`; the cadrumo one is `logs\mcp-server-Cadrumo tax assistant console.log`.

## Auth seeding (feasible)

Because the token cache is DPAPI-user-bound rather than profile-bound, copying the curated set (`config.json`, `Local State`, `Network\Cookies`, `Local Storage`, `Session Storage`) from a blessed source profile into a fresh isolated user-data dir lets the SAME Windows user decrypt it. This is the same seeding shape as the `.credentials.json` copy in `dev/packaging/smoke_plugin_install.py`. One-time interactive login into the source profile is the auth root; every run is clean except the seeded auth.

## Launch / drive wall (characterized)

- Custom Electron flags (`--remote-debugging-port`, `--user-data-dir`) reach the app only through MSIX activation: `IApplicationActivationManager::ActivateApplication` or `Invoke-CommandInDesktopPackage`.
- The standing agent context is elevated, SessionId 0, non-interactive (`WindowsPrincipal.IsInRole(Administrator)` true, `GetProcess.SessionId` 0, `Environment.UserInteractive` false). From it, both `Invoke-CommandInDesktopPackage -Command` and `ActivateApplication` return `E_ACCESSDENIED` (0x80070005) — Store activation is refused to an elevated Session-0 caller.
- Bridged into the interactive session via a scheduled task (`LogonType Interactive`, `RunLevel Limited`), `ActivateApplication` SUCCEEDS (returned a real process id, session=1, interactive=True).
- Electron single-instance: while the operator's Desktop is already running, the activated process forwards its argv to the primary and EXITS (the returned pid was gone immediately; the process count stayed 18; no debug port opened; the isolated user-data dir stayed empty). Startup-only Chromium flags (`--remote-debugging-port`) only take effect on the primary at its own startup. So the harness must be the PRIMARY: no other Desktop instance running at launch.

## Residual unknown

Whether `Claude.exe` honors `--user-data-dir` (versus a hardcoded `app.setPath('userData', ...)`) could not be confirmed without primary-instance ownership, which requires closing the running Desktop. The harness resolves this on the first real run and aborts BEFORE driving if the isolated profile shows no post-launch runtime state; the pre-designed fallback is a direct `Claude.exe` launch with a redirected `APPDATA` (`desktop_capture.launch_desktop_direct_appdata`).

## MCP tool-call proof

The cadrumo MCP server records one telemetry object per served call carrying a typed `transport` field (`inprocess` / `subprocess` / `subprocess_fallback`) plus the attested environment-CLI path/sha (commit `60d7120e22`). Desktop captures that on the server's stderr in the isolated profile's `logs\mcp-server-*.log`. The harness parses it (`desktop_capture.parse_mcp_server_log`) and gates capture success on a genuinely-served call whose RESULT carried no error marker (`McpToolCall.succeeded`), not merely a dispatched call — closing the connected-plus-dispatched false-pass.

## Cowork assessment (design-only)

Claude Cowork runs at claude.ai in a browser, so its capture would be Playwright driving a persistent-auth browser profile (a one-time interactive login persisted in a dedicated harness browser user-data dir, clean per run otherwise) against the claude.ai chat surface, with the same MCP/tool-call proof read from the connected server's telemetry rather than a debug port. It is a distinct decision from the Desktop MSIX shape and is not built in this pass; recommended as the next capture surface after the Desktop harness proves out.
