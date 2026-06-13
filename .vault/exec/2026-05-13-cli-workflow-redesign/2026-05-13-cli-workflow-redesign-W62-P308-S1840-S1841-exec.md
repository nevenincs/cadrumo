---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P308.S1840-S1841'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
---

# `cli-workflow-redesign` `W62.P308.S1840-S1841`

Added runtime CLI behavior tests for registry corpus output and replaced CLI-local corpus lookup with application registry service delegation.

## Description

The registry corpus CLI tests now invoke the real `aeat app registry citations` command path against a minimal valid normative corpus passed through `AEAT_NORMATIVES_ROOT`. The tests assert text output and JSON output through the root `--format` contract using the application report shape: citation rows expose `topic_slugs`, citation show exposes `articulo.cite`, and `related_topics` is present on the typed payload.

The CLI corpus module now calls `aeat.application.registry` services for citation and manual list/show/rules/verify operations. It no longer imports normatives lookup APIs, manual loading APIs, manual rule APIs, JSON rendering, or command-local error strings. The CLI layer parses arguments, calls typed application services, and renders typed reports through `_emit`.

The stale `cli.registry.manuals.errors.unknown_section` locale key was removed because manual section refusal now belongs to the application registry error path.

## Review Remediation

Review flagged the first S1840 tests as a false-positive risk because they locked the old CLI-local payload shape. The tests were corrected to assert the application report contract, and S1841 replaced the CLI implementation so those tests now prove service delegation rather than preserving the old direct-domain path.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_registry_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/locales`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_registry_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_registry_corpus.py -q`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/application/topics/test_catalogue.py src/aeat/entrypoints/cli/test_registry_cli.py::test_registry_retained_commands_reject_command_local_json_flag -q`
- `uv run --no-sync python -m aeat.locales audit`

The focused registry corpus CLI suite passed with 12 tests. The broader W62 slice passed with 47 tests. Code review returned no findings.
