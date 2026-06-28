---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase1-step3-review-audit]]'
---



# `calculation-truth-registry` `Phase 1` `Step 3`

Extended the registry CLI closure report and updated the execution plan to keep
the Modelo 130 live dependency visible as pending work.

- Modified: `src/aeat/entrypoints/cli/registry.py`
- Modified: `src/aeat/entrypoints/cli/test_registry_cli.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase1-step3-review.md`

## Description

`inspect` and `verify` JSON output now includes one closure record per committed
modelo revision. The detail exposes revision legal/source references, export
layout ids and field totals, deadline periods, portal guard policy ids, workbook
parity classification, and support/removal decision counts.

The CLI tests exercise the public command surface against committed registry
data and assert structural closure invariants rather than redefining Modelo 130
schema details in the test body.

The plan now marks the Phase 1 CLI closure-detail row complete and leaves an
explicit pending Modelo 130 row for previous-filing bindings that depend on the
future Modelo 100 registry/parser snapshot.

## Tests

`uv run pytest src\aeat\entrypoints\cli\test_registry_cli.py -q`

`uv run ruff check src\aeat\entrypoints\cli\registry.py src\aeat\entrypoints\cli\test_registry_cli.py`

`uv run ty check src\aeat\entrypoints\cli\registry.py src\aeat\entrypoints\cli\test_registry_cli.py`

`uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`

`git diff --check`
