---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:07e11fec0ca00c7b5741e010313db5b08444016046d1dacd036d8137b2abbca8'
step_id: 'S22'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Declare which of archive import file and artifact is the primary local input

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `verify:` `archive import declares --file primary, --artifact auxiliary` -> `pass`

## Notes

No code change was required: the declaration landed correctly during the W01
locus sweep. `--file` is the required capsule and is primary; `--artifact` is
optional and its presence selects the machine-secret variant, so it configures
the operation rather than being its subject.
