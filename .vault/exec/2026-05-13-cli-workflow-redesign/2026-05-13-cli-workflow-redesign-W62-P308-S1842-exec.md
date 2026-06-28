---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P308.S1842'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
---

# `cli-workflow-redesign` `W62.P308.S1842`

Validated that rejected topic/help command vocabulary is absent from accepted command discovery and accepted help text.

## Description

The registry corpus CLI tests now inspect the actual Click command tree through the cached CLI command and assert that no command named `topic`, `topics`, or `help` appears at the root, app, registry, citations, or manuals levels. The tests also render accepted help surfaces and assert that rejected command phrases such as `aeat help`, `aeat topic`, and `aeat app topic` are absent.

The tests do not invoke rejected command paths. This keeps S1836 intact: the suite validates the accepted discovery and help surfaces without preserving behavior for removed commands.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_registry_corpus.py`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_registry_corpus.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_registry_corpus.py -q`
- `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/application/topics/test_catalogue.py src/aeat/entrypoints/cli/test_registry_cli.py::test_registry_retained_commands_reject_command_local_json_flag -q`
- `uv run --no-sync python -m aeat.locales audit`

The registry corpus CLI suite passed with 14 tests. The final W62 slice passed with 49 tests. Code review returned no findings.
