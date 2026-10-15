---
tags:
  - '#reference'
  - '#session-lifetime-repair'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:5307d4b4e459a45cc6eef9bae33bbf706673d3b6da9d3b13911689a3efcd390a'
related: []
---

# `session-lifetime-repair` reference: `Active session lifetime and shutdown evidence`

## Summary

Initial investigation found no human-input renewal path and a TUI failure path that labeled unavailable status as expiry. Historical native crash dumps independently identify Python buffered-input finalization failure. This record describes the pre-repair evidence; the audit and execution ledger track repairs and verification.

## Context

User reported active-use logout and desktop termination in the Debug package and explicitly authorized continued investigation and fixes. Preserve the real profile; tests use synthetic custody.

## Findings

Inspected 2026-10-15 checkout and Debug package. Human admission freezes expires_at at the smaller idle/absolute deadline (src/cadrumo_runtime/application/session_authority_admission.py:352). Session refresh supports only API roots (same file:430 and src/cadrumo_runtime/host/profile_connection_sessions.py:345). Worker refresh similarly refuses human leases (src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:106). TUI background status exceptions become expired (src/cadrumo/entrypoints/tui/app.py:362); Windows unknown observations can retire login-bound leases (src/cadrumo_runtime/application/session_authority_core.py:92). Receipt sealing keys are zeroized after mint; no extension implementation exists (src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:1046).

Latest local logs on 2026-10-15 show successful TUI login at 07:37:50Z, user-profile.view success at 07:44:16.846Z, refusal os_session_unavailable at 07:44:17.663Z, requested supervisor stop at 07:44:17.729Z, TUI expired/reconnect at 07:44:17.777Z, runtime exit64 supervisor_stop at 07:44:17.947Z, then connection refusal, terminal termination and webview write_failed. The cause of the initial desktop shutdown is not established. Earlier Windows WER reports record Release runtime/agent-service c0000005 python313.dll offset 2a7d8f, a separate native failure. Subsequent symbolized minidump analysis proves _enter_buffered_busy during TextIOWrapper finalization followed by a null dereference in fatal_output_debug; blocked daemon stdin readers remain on the stacks. Matching Python3.13.11 PDB provenance and dump hashes are recorded in build/crash-symbols/session-crash-findings.txt.

## Sources

C:/Users/hello/AppData/Local/cadrumo/logs/cadrumo.log and cadrumo-native.jsonl, final Debug run 2026-10-15. Windows Application event log IDs1000/1001 for 2026-10-15. Source locators above; packaged runtime admission and connection-session files match source text.
