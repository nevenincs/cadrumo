---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b2620c491f97a1941a492fa2159b93963d4253ed16b820e62c54bf905d759037'
step_id: 'S15'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Re-verify every required_text phrase on the two Orden HAC/1526/2024 entries against the replaced BOE text, replacing the unaccented phrasings that only matched the paraphrase

## Scope

- `src/cadrumo/_data/registry/aeat/legal/censo.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/censo.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
