---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1148af04ad94ce8e8147649379b67ed70c0a23e985581311981fee8754efdf9c'
step_id: 'S13'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Prove the placement gate bites by mounting a filing leaf under config from outside the repository

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `verify:` `scratchpad proof: filing-under-config, bootstrap-under-app, both-signals, empty-graph` -> `pass`

## Notes

The proof runs entirely from a scratchpad script by substituting the gate's
subject accessor; no tracked file under `src/` is mutated, so a crashed run
leaves no residue and a peer sweep cannot commit the mutation.
