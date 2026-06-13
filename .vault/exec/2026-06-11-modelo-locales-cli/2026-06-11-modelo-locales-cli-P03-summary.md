---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# `modelo-locales-cli` `P03` summary

Phase P03 added focused verification for the modelo localization manager, CLI command surface, catalogue isolation boundary, registry-loader consumption, and feature-surface gate evidence.

- Modified: `src/aeat/locales/_modelo_manager.py`
- Created: `src/aeat/locales/tests/test_modelo_manager.py`
- Created: `src/aeat/locales/tests/test_modelo_cli.py`
- Modified: `src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py`
- Modified: `.vault/plan/2026-06-11-modelo-locales-cli-plan.md`

## Description

The manager tests copy real bundled Modelo 130 registry data into temp roots and cover coverage inventory, scaffold preservation, stale-key cleanup, set/remove writes, unknown-key refusal, and path containment. Those tests found and fixed a scaffold behavior issue: missing locale files are no longer created for scopes with no expected translation keys.

The CLI integration tests cover coverage, audit, scaffold check, scaffold write, set, remove, invalid-key refusal, eager YAML isolation, and official Spanish label preservation. The registry loader test proves manager-written TOML is accepted by `load_modelo_directory`.

The feature-surface gate evidence is recorded in the plan. Ruff, focused pytest, and the plan check passed. The feature-scoped vault check remains blocked by an unrelated live-censo-calendar-reconciliation exec filename structure error that the feature filter still reports.
