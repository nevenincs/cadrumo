---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:728004e677a6fa34be2380fa35db35d1ac08f665e9bca35833f04825dd2c33b3'
step_id: 'S05'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Move the casilla commentary displaced from the article 48 excerpt into the legal entry notes and re-verify every required_text phrase against the replaced corpus text

## Scope

- `src/cadrumo/_data/registry/aeat/legal/irpf.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
