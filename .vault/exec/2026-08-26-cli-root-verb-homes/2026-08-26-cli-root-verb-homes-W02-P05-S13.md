---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:82864ed5be59bcb1de5dbbca779e6c7d702f70c69734c0e38fa09cbd92273dc2'
step_id: 'S13'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Prove the placement gate bites by mounting a filing leaf under config from outside the repository

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `verify:` `scratchpad proof: filing-under-config, bootstrap-under-app, both-signals, empty-graph` -> `pass`

## Notes

The proof runs entirely from a scratchpad script by substituting the gate's
subject accessor; no tracked file under `src/` is mutated, so a crashed run
leaves no residue and a peer sweep cannot commit the mutation.
