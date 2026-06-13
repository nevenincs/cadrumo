---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P307.S1835'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
---

# `cli-workflow-redesign` `W62.P307.S1835`

Verified the entrypoint command tree contains no topic or help command registrations outside the approved `aeat app registry` registry-corpus path.

## Description

The Typer registration tree exposes only `config` and `app` at the root. The app namespace exposes `overview`, `ledger`, `live`, `modelo`, `registry`, and `review`. It does not expose `topic`, `topics`, or a standalone `help` command. The registry namespace owns the accepted `citations` and `manuals` corpus surfaces.

No source deletion was required for this step because the rejected topic/help registrations were already absent from the current command tree.

## Tests

Passed:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_surface.py::test_retired_invoice_declaration_and_topic_surfaces_are_not_user_facing src/aeat/entrypoints/cli/test_registry_corpus.py::test_no_parallel_registry_corpus_surface_exists src/aeat/entrypoints/cli/test_registry_corpus.py::test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry -q`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/_registry_corpus.py`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/_registry_corpus.py`

The focused CLI rejection slice passed with 3 tests.
