---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P306.S1834'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-s1834-code-review-audit]]"
---

# `cli-workflow-redesign` `W62.P306.S1834`

Recorded registry corpus service failures and registry log fields through the central error and logging drivers.

## Description

Registry citation and manual application services now emit structured registry log fields for list, show, and invalid-input paths. Citation lookup failures include the registry service, normative id, and article selector. Manual section refusals, manual id refusals, manual rule-kind refusals, and unsupported topic-locale refusals now include service-specific context on `RegistryApplicationInputError` so the central error envelope preserves the operational fields.

The CLI remains uninvolved in registry business logic. It continues to receive typed application reports and central error envelopes instead of formatting errors or inspecting domain exceptions itself.

## Review Remediation

The S1834 code review identified missing structured logging for citation article failures, missing context/logging for unsupported locale errors, and a missing regression assertion for unsupported-locale log fields. All three findings were remediated in the registry service and tests.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/application/registry`
- `uv run --no-sync ty check src/aeat/application/registry`
- `uv run --no-sync python -m aeat.locales audit`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py -q`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py src/aeat/application/topics/test_catalogue.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_envelope.py -q`

The focused registry corpus suite passed with 15 tests. The broader registry, topic, CLI boundary, and core error slice passed with 50 tests.
