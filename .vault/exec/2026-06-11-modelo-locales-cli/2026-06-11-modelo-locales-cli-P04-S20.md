---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
step_id: 'S20'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P04.S20 codify modelo locale CLI authority

Scope: `.vaultspec/rules/rules/project/modelo-locales-cli-authority.md`.

## Description

- Verify durability criteria against the accepted ADR, execution evidence, and review audit.
- Search existing rules and confirm `aeat-locales-cli` covers eager YAML catalogues but not registry-local modelo TOML authority.
- Scaffold `modelo-locales-cli-authority` through `vaultspec_core spec rules add`.
- Author the project rule with Rule, Why, and How sections.
- Verify the rule through `vaultspec_core spec rules show modelo-locales-cli-authority`.

## Outcome

The project now has a standing rule that modelo schema-local translation TOML must be managed through `python -m aeat.locales modelo ...`.

## Notes

The rule is deliberately separate from `aeat-locales-cli`, which remains focused on eager `src/aeat/locales/*.yml` catalogue work.
