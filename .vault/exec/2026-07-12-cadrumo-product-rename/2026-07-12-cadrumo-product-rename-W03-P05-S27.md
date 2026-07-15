---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S27'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update the optional-extra authority and every directly generated runtime install remedy to current `cadrumo[...]` metadata, with real degradation tests

## Scope

- `src/cadrumo/core/_optional_extras.py`
- `optional-extra consumers`
- `error registries`
- `agent/MCP/search/corpus degradation surfaces and direct tests`

## Description

- Point the optional-extra authority at `cadrumo[extra]` installation commands.
- Converge directly emitted Google, browser, Anthropic, agent, search, and corpus-source remedies on current metadata.
- Update real degradation and error-envelope assertions without introducing test doubles.
- Preserve third-party import names and AEAT authority, Sede, evidence, and registry semantics.

## Outcome

Every active Python runtime remedy uses the Cadrumo distribution and a declared
extra. The real lean-core, missing dependency, search, corpus companion, and MCP
refusal tests pass together: 19 passed.

## Notes

The existing meta-path import blocker remains the real import-isolation mechanism;
this step introduced no mocks, patches, monkeypatches, skips, or expected failures.
Historical rule names and AEAT authority identifiers were not renamed.
