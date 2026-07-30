---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S128'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace flat scoped reset with reset start, status, and resume schemas

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

- Confirm the three durable reset result schemas are registered in the named payload module.
- Confirm no flat scoped reset schema survives alongside them.

## Outcome

The named surface registers `config.reset.start`, `config.reset.status`, and `config.reset.resume`, each wrapping the shared reset operation payload. The flat `config.reset` key is absent from the live registry, so the nested grammar fully replaced it rather than shipping beside it.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
