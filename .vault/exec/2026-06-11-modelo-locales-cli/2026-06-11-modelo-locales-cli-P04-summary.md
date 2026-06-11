---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# `modelo-locales-cli` `P04` summary

Phase P04 migrated seeded schema-local locale files under CLI control, recorded campaign usage, codified the CLI authority rule, ran verification gates, and handed off the remaining translation campaigns.

- Modified: `src/aeat/_data/registry/aeat/modelos`
- Modified: `src/aeat/locales/_modelo_manager.py`
- Modified: `src/aeat/locales/tests/test_modelo_manager.py`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vaultspec/rules/rules/project/modelo-locales-cli-authority.md`
- Modified: `.vault/plan/2026-06-11-modelo-locales-cli-plan.md`
- Modified: `.vault/research/2026-06-11-registry-schema-localization-research.md`

## Description

The seeded non-Spanish schema-local locale files for M100, M130, M200, and M303 were scaffolded through `python -m aeat.locales modelo scaffold`. M130 remains the complete exemplar, while M100, M200, and M303 now have full placeholder scaffolds with their existing translated leaves preserved.

P04 exposed and fixed a manager bug in all-revision inventory deduplication: revision-local keys now include `revision_id` in their identity, preventing translations from one revision from being treated as stale because the same casilla id appears in another revision. The M100 seeded leaves were restored through `python -m aeat.locales modelo set`.

The plan now records campaign usage and seeded coverage, the project rule `modelo-locales-cli-authority` codifies the CLI-only TOML workflow, and the research handoff records the remaining translation backlog. Focused ruff, pytest, generic locale audit/scaffold checks, seeded coverage, and plan check passed.
