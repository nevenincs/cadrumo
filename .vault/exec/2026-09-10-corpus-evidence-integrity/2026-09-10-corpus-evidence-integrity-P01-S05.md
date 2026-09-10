---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:6edd7a9164b6593d4b86c04df2bab85c0b9b217e47b029e94dff83df94993dd3'
step_id: 'S05'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Move the casilla commentary displaced from the article 48 excerpt into the legal entry notes and re-verify every required_text phrase against the replaced corpus text

## Scope

- `src/cadrumo/_data/registry/aeat/legal/irpf.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
