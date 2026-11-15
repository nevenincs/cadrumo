---
tags:
  - '#adr'
  - '#desktop-shell'
date: '2026-11-15'
modified: '2026-11-15'
body_schema: 'body-v2'
body_hash: 'sha256:ceaef05d742dc6a2b5535dcd05d2ee8779cc341c4333a41af79e185bfb6319f8'
related:
  - '[[2026-11-15-desktop-shell-console-environment-reference]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-12-desktop-agent-host-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
  - '[[2026-10-13-native-agent-adr]]'
  - '[[2026-10-13-agent-attachments-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
---
# `desktop-shell` adr: `The desktop console takes the agent service's provider homes, harness workspace and tool server for the signed-in profile` | (**status:** `accepted`)

Accepted by the operator on 2026-11-15 16:59 (relayed by PRIME, ruling 16:59) as written, including plaintext provider program transcripts in the profile's provider home and the console-kind amendment of `2026-10-04-desktop-shell-adr`. Option B was rejected by the operator on 2026-11-15 15:59.

## Problem Statement

The desktop console starts provider command-line programs (`claude`, `codex`) that the person runs, but carries none of the agent service's provisioning for the profile. It has no provider home where the service's provider sign-in keeps credentials (cadrumo-agent `src/cadrumo_agent/providers/_hosted_provider_home.py:18-36`, `providers/_native_role.py:109`). It has no workspace with the skills, rules and `CLAUDE.md`/`AGENTS.md` that cadrumo-agent materialises (`harness/workspace.py:244`). It has no `cadrumo-mcp` registration, which the service gives only to the gateway (`src/cadrumo_agent_service/host/launch_environment.py:276-342`). Nothing refreshes the console on sign-in, sign-out or profile change. Operator order 2026-11-15 14:28; PRIME rulings 14:34 and 14:55 chose option A and require this record before any code.

## Considerations

- The console builds its environment from the filtered child environment, sets its working directory to the shared console workspace and clears the inherited environment (`native/desktop/src-tauri/src/terminal/mod.rs:56-93`, `terminal/session.rs:231-241`, `environment.rs:174-266`, `native/platform/src/storage.rs:557-600`).
- cadrumo-agent owns authored content, workspace materialisation and provider homes; Cadrumo serves no persona, rule or skill text (`2026-07-02-agent-harness-refoundation-adr`, 2026-10-21 amendment).
- The agent service owns agent processes, credential interpretation and stores; `cadrumo_runtime` has no agent verbs (`2026-10-13-native-agent-adr`, `2026-10-12-desktop-agent-host-adr`).
- `CADRUMO_AGENT_*` names reach only the gateway (`2026-10-13-canonical-environment-application-internals-adr`).
- An agent works only inside the signed-in profile (`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`).
- The 2026-10-07 terminal-workspace amendment of `2026-10-04-desktop-shell-adr` keeps all terminal kinds on one pinned workspace and environment and says profile details are not conveyed through new environment variables; this decision narrows that for the `console` kind.

## Considered options

- **A: an agent-service read that the host composes into the console.** Chosen: one owner per fact, no agent layout in Rust, nothing private in the window.
- **B: a per-profile list of environment variables the person edits.** Rejected by the operator (2026-11-15 15:59).
- **C: the host derives provider homes and the workspace itself.** Rejected: it duplicates cadrumo-agent's layout in the Rust host and drifts when that layout changes.

## Constraints

1. The agent service gains one read-only administration read, `console_environment`, for the signed-in profile, answering `{environment, working_directory, revision}`.
2. The environment holds only the provider home names (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`), the values needed to locate the harness workspace cadrumo-agent materialised for that profile, and the `cadrumo-mcp` tool server registration in each provider's own form. It holds no `CADRUMO_*`, `PYTHON*`, `AEAT_*` or `FINANCIAL_*` name and no name the console filter clears.
3. No secrets. Provider credentials stay in the provider homes and never enter the map, logs, diagnostics, arguments or the window. The service writes no persona, rule or skill text; cadrumo-agent materialises it.
4. The working directory is the profile's harness workspace, never inside the bucket or capsule custody tree.
5. The host applies the map only to the `console` kind, at `terminal_open`, merged over the existing filtered child environment; for names the service owns the service value wins, and the existing filter still applies to the merged result. The `python` and `tui` kinds are unchanged.
6. The host re-reads on Cadrumo profile sign-in, sign-out and profile change. The window receives only `console-environment-changed {revision}`, never content. With no signed-in profile or no service, the console gets the base environment and the shared console workspace, never the previous profile's values.
7. A console with no running process is relaunched by the window. A console with a running process shows a notice and a restart door (`terminal_close` then `terminal_open`); it is never killed silently.
8. Admission is not widened: whether a `cadrumo-mcp` started by a console program is admitted is decided by current runtime and MCP admission alone.
9. On acceptance, the 2026-10-07 amendment of `2026-10-04-desktop-shell-adr` gains this amendment: "Amendment (2026-11-15, under `2026-11-15-desktop-shell-console-environment-adr`): the `console` kind adds the agent service's console environment for the signed-in profile over the pinned environment, and starts in that environment's working directory when one is given; otherwise it keeps this workspace. The `python` and `tui` kinds are unchanged. The added values name per-profile provider homes, the harness workspace and the tool server registration; they carry no credential, session, receipt or key. Authentication still uses native peer verification and the profile receipt flow, and none of these values grants authority."

## Implementation

We will add `console_environment` to the agent service's authenticated administration channel and compose the console from it in the Tauri host, refreshing it on profile authority changes.

Implementation hypotheses, which may change within the constraints:

- The service obtains provider home paths and the workspace path from a cadrumo-agent read or materialisation call rather than re-deriving them; today `materialise_workspace` is reachable only through `python -m cadrumo_agent.harness` (cadrumo-agent `src/cadrumo_agent/harness/__main__.py:21`), so cadrumo-agent needs a callable entry.
- The revision is an opaque digest of the answer; the no-profile state has its own revision.
- The read lives in `src/cadrumo_agent_service/service_administration.py`; the host side in `native/desktop/src-tauri/src/agent/admin.rs` and `terminal/mod.rs`.
- Registration takes the form of `.mcp.json` in the workspace for Claude Code and `config.toml` in `CODEX_HOME` for Codex.

Test obligations, on a synthetic profile without mocking the component under test: the real console shows the provider home, skills, rules, `CLAUDE.md`/`AGENTS.md` and the tool server registration, refreshed after sign-in, sign-out and profile change; after sign-out none of the previous profile's values remain; a known credential string appears in no map value, log, IPC payload or window event; window IPC carries only the revision; the filter still clears its names after the merge; a running process survives a change and gets the notice; every test sign-in signs out at teardown.

## Rationale

Option A keeps one owner for each fact: cadrumo-agent owns provisioning, the service owns credentials and process policy, and the host only composes. The window learns nothing private. Running the person's provider programs in the same homes and workspace as the agent makes the console match the agent column without a second configuration surface. Option C fails on ownership; option B answers a different question that only the operator can decide.

## Consequences

- The person's provider programs use the profile's provider sign-in, skills and tools.
- Accepted cost: a program that keeps running after sign-out or a profile switch keeps its old home until the person restarts it; its `cadrumo-mcp` calls are refused once the profile differs.
- Provider programs write their own transcripts into the provider home. This record makes no claim about protecting them at rest; whether that is acceptable under the private-data rule is for the operator.
- Reconsider if the operator accepts option B, if cadrumo-agent changes its provider home layout or hosting contract, or if admission for console-started tool servers is refused by design.
