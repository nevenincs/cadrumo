---
tags:
  - '#audit'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-07-17'
body_hash: 'sha256:e025b38a35b8fbab72afe6f4f48b0e5fa8b12ba3308a6a45c5d9832896e21f0f'
related:
  - '[[2026-05-01-corpus-data-hydration-plan]]'
  - '[[2026-05-01-corpus-data-hydration-adr]]'
  - '[[2026-05-01-corpus-data-hydration-research]]'
---

# `corpus-data-hydration` Code Review

RULE-001 | RESOLVED | Year Mismatch in Modelo 111 2024 Rule References
Fixed: All rule references in `modelo_111` JSON files now use the correct year prefix matching the filing period (e.g., `modelo_111.2024` for 2024 filings).

I18N-001 | RESOLVED | Missing Catalan (ca) Translations
Fixed: All hydrated records now contain the mandatory `ca` key in `label` and `help` fields, satisfying the project's quad-lingual i18n contract.
