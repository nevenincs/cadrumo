---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:a4709c584debe53b13e67b3f8d4475ee2448e36df6df98e2e5ebf5c648badf5e'
step_id: 'S152'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace sandbox-use identity gating with canonical config switch handling

## Scope

- `src/cadrumo/entrypoints/mcp/_identity_gate.py`

## Description

- Read the MCP identity gate and confirm the identity-changing verb set uses the canonical switch grammar.
- Confirm no sandbox-use gating survives.

## Outcome

The gate is keyed on the canonical switch grammar. The closed set of active-identity-changing verbs is login, profile create, and logout, and the site records that login is what enters a sandbox, by its canonical label, so no separate sandbox-use door is gated or needed.

The reasoning at the site is precise about scope: editing or renaming the current profile does not change who is active and so deliberately does not re-arm the gate, while a profile switch does. The identity-read set that clears the gate is equally explicit, and the console harness read is admitted with a recorded rationale that it already surfaces the active identity.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
