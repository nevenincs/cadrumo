---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:740b36ddafa334c3dd9363596332bcaa650588d90b8428885487478ed03829fd'
step_id: 'S16'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Re-verify every required_text phrase on the two Orden EHA/3290/2008 entries against the replaced BOE text and correct the reviewed_by claim of a verbatim BOE fetch that the bundled file contradicts

## Scope

- `src/cadrumo/_data/registry/aeat/legal/irnr.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/irnr.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
