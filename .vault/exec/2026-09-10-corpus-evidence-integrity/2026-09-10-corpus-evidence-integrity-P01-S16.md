---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:8343d165fc877e79773eb496caa9725480a9061d12039c66e6482cf8c50e5a4e'
step_id: 'S16'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Re-verify every required_text phrase on the two Orden EHA/3290/2008 entries against the replaced BOE text and correct the reviewed_by claim of a verbatim BOE fetch that the bundled file contradicts

## Scope

- `src/cadrumo/_data/registry/aeat/legal/irnr.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/irnr.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
