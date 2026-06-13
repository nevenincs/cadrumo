---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P308.S1839'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-s1839-code-review-audit]]"
---

# `cli-workflow-redesign` `W62.P308.S1839`

Added service tests for topic-backed citation and manual registry projections.

## Description

The registry service test suite now exercises citation list and citation show projections through a real normative loader against a minimal valid corpus directory. The tests use a typed topic catalogue and assert reference topic slugs, localized topic projection text, article projection fields, citation text, and related topic projection. Existing manual projection tests continue to cover manual listing, manifest metadata, verification, and rules.

This keeps verification in the application service layer and does not add CLI-local lookup, formatting, or business logic.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/application/registry/test_corpus.py`
- `uv run --no-sync ty check src/aeat/application/registry/test_corpus.py`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py -q`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py src/aeat/application/topics/test_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_registry_corpus.py -q`
- `uv run --no-sync python -m aeat.locales audit`

The focused registry service suite passed with 17 tests. The broader W62 slice passed with 44 tests. Code review returned no findings.
