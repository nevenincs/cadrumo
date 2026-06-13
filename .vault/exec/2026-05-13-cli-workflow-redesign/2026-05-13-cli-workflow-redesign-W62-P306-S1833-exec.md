---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P306.S1833'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
---

# `cli-workflow-redesign` `W62.P306.S1833`

Resolved registry topic i18n through the central locale backend in the application service layer.

## Description

Registry corpus service functions now resolve a stable locale for each report before rendering topic titles and bodies. The default path calls the central `output_language()` resolver once for the report and passes the resolved locale explicitly to `tr()` for every topic projection. Callers may pass an explicit supported locale for application tests or backend composition; unsupported locale values raise `RegistryApplicationInputError`.

This keeps topic prose out of CLI handlers. The CLI continues to consume typed application reports instead of embedding topic text, translation keys, or manual rendering logic.

## Tests

Passed:

- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py -q`
- `uv run --no-sync pytest src/aeat/application/topics/test_catalogue.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py -q`
- `uv run --no-sync ruff check src/aeat/application/topics src/aeat/application/registry src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py`
- `uv run --no-sync ty check src/aeat/application/topics src/aeat/application/registry`

The focused registry corpus suite passed with 12 tests. The broader topic and registry slice passed with 38 tests. Code review returned no findings.
