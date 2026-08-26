---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5a1ae15b9c6d2d20a57a2364dc601e6de7f0bc5bbaacdde8880ce03f409939cf'
step_id: 'S23'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Prove config repair integrity registry and app registry verify report the same authority state

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `verify:` `read build_registry_integrity_report vs verify_registry_tree` -> `pass`

## Notes

The proof returned the opposite of the plan's expectation. `verify_registry_tree`
validates the authority and runs `required_text` corpus checks;
`build_registry_integrity_report` additionally builds a representative `M100`
snapshot and so exercises the snapshot-build gate. Neither subsumes the other,
so the retirement in S24 does not proceed.
