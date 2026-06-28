---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S15'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P03.S15 add catalogue isolation regression tests

Scope: `src/aeat/locales/tests/test_modelo_cli.py`.

## Description

- Add CLI regression coverage proving modelo-local commands do not mutate eager `src/aeat/locales/*.yml` catalogues.
- Add CLI regression coverage proving an English schema-local label update does not mutate the official Spanish schema label.
- Reuse real copied Modelo 130 registry data for the isolation checks.

## Outcome

The CLI test suite now guards the core architecture boundary: modelo schema-local writes stay in registry-local TOML, while normal application locale YAML and legally-bound schema labels remain separate.

## Notes

Verification passed with `ruff check src/aeat/locales/tests/test_modelo_cli.py src/aeat/locales/cli.py src/aeat/locales/_modelo_manager.py` and `pytest src/aeat/locales/tests/test_modelo_cli.py -q -m integration`.
