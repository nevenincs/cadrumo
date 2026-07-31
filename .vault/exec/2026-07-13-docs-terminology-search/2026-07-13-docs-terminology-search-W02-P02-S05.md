---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:b8a3c03ee5025a59c6b3bfc71fb2fe83fe1c3d1dcfd1128c4b64ddca34e221ed'
step_id: 'S05'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Author the preprocess rule file for the four corpus source kinds and add the strict preprocess-check repo gate test

## Scope

- `.vaultragpreprocess.toml`
- `dev/docs/preprocess/tests/`

## Description

- Author repo-root `.vaultragpreprocess.toml`: four rules routing normatives
  HTML, corpus PDFs, `.xls`, and `.xlsx` through the hook command with
  `on_error = "skip"` and per-kind timeouts.
- Validate with `vaultspec-rag preprocess check --json` (v0.2.28): 4 rules.
- Add the CI-safe structural gate in `dev/docs/preprocess/tests/test_hook.py`
  (validates the TOML shape without importing the upstream package).

## Outcome

Committed in `485ac85614`. Two live catches: the original `*.xls*`
pattern also matched `.xls.extracted.md` sidecars (split into explicit
`.xls`/`.xlsx` rules), and upstream requires the
`VAULTSPEC_RAG_PREPROCESS_ENABLED=1` opt-in before rules take effect.

## Notes
