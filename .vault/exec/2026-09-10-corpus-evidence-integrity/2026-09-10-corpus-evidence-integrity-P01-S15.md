---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:82a3205860e39e44bbcbe234a4378d9fc3320ac89eab946c397e5c9c89ff3447'
step_id: 'S15'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Re-verify every required_text phrase on the two Orden HAC/1526/2024 entries against the replaced BOE text, replacing the unaccented phrasings that only matched the paraphrase

## Scope

- `src/cadrumo/_data/registry/aeat/legal/censo.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/censo.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
