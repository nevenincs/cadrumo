---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W01.P005'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]"
---

# `cli-workflow-redesign` `W01.P005`

Closed plan rows:

- `W01.P005.S0025`
- `W01.P005.S0026`
- `W01.P005.S0027`
- `W01.P005.S0028`
- `W01.P005.S0029`
- `W01.P005.S0030`

## Description

W01.P005 tightened the active CLI exposure for the accepted root and lifecycle contract. The mounted command tree remains rooted under `aeat config` and `aeat app`; active help surfaces now render accepted operator vocabulary without leaking translation keys or retired command language.

The ledger row allocation option now uses the accepted operator spelling `--allocate` instead of the retired `--split` spelling, while still routing through the existing backend `LedgerSplit` value object and `update_ledger_review` service. The config-init wizard question that stores profile key `declaration.type` now exposes the operator-facing flag and field as `taxation-type`, preserving backend storage compatibility without keeping the rejected CLI word in active help.

The active English help contract is pinned by behavior tests that inspect rendered command help only. The tests avoid ADR names, wave ids, phase ids, and execution metadata.

## Modified Paths

- `src/aeat/application/wizard/_catalogue.py`
- `src/aeat/application/wizard/_setup_answers.py`
- `src/aeat/application/wizard/_verifier.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_cli_surface.py`
- `src/aeat/entrypoints/cli/test_workflow_surface.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

- `uv run --no-sync ruff check src/aeat/application/wizard/_catalogue.py src/aeat/application/wizard/_setup_answers.py src/aeat/application/wizard/_verifier.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/entrypoints/cli/test_workflow_surface.py`: passed.
- `uv run --no-sync python -m compileall -q src/aeat/application/wizard src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/entrypoints/cli/test_workflow_surface.py`: passed.
- Focused CLI/wizard slice covering active help vocabulary, ledger allocation, config wizard runtime, and verifier contracts: `24 passed`.
- Broader apex/root slice covering config/app roots, wizard, auth, review, retired surfaces, CLI help, and CLI workflow behavior: `96 passed`.
