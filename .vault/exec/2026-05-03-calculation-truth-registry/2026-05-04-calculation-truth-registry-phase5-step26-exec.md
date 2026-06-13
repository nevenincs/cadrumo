---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step26`

Expanded workbook verification from a Modelo 130-specific checklist item into a
registry-wide validation gate for every supported modelo.

- Modified: `.vault/adr/2026-05-03-calculation-truth-registry-pending-adr.md`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/_workbook_parity.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_workbook_parity.py`
- Modified: `src/aeat/entrypoints/cli/registry.py`

## Description

The ADR now states that every modelo revision must declare workbook parity
coverage as part of registry validation. Formula-bearing official workbooks must
have executable parity outputs; static layouts, record designs, unsupported
binary XLS files, and unreadable artefacts are evidence decisions, not passed
calculation parity.

The plan now includes a per-modelo workbook verification checklist for every
supported modelo. The shared completion contract also requires identical
synthetic inputs to feed the registry engine and workbook or simulator parity
surface, with non-executable workbook coverage recorded before production
readiness.

The registry schema rejects contradictory workbook parity declarations:
formula-bearing workbooks require a runner, and a runner is valid only for
formula-bearing coverage. The registry validator now rejects revisions that do
not declare official workbook parity coverage.

Workbook backend verification now scans every discovered artefact by default.
The CLI keeps `--limit` as an explicit operator override, but an unbounded scan
is the default verification gate.

The full official workbook corpus scan found 72 workbook artefacts: 47
formula-bearing workbooks, 25 unsupported binary XLS files, and no failed
workbook scans. Excel COM was available as the local runner.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_workbook_parity.py -q`
- `uv run pytest src/aeat/domain/calculations/registry -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/_workbook_parity.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_workbook_parity.py src/aeat/entrypoints/cli/registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/_workbook_parity.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_workbook_parity.py src/aeat/entrypoints/cli/registry.py`
- Direct corpus verification with `verify_workbook_backend` over
  `corpus/aeat_official/disenos_registro` and no scan limit.
- Direct registry validation over committed registry TOML.
- `git diff --check -- .vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md .vault/adr/2026-05-03-calculation-truth-registry-pending-adr.md .vault/exec/2026-05-03-calculation-truth-registry/2026-05-04-calculation-truth-registry-phase5-step26.md src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/_workbook_parity.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_workbook_parity.py src/aeat/entrypoints/cli/registry.py`

The focused domain tests passed. The CLI registry test selection is currently
blocked before registry import by an invalid locale YAML file in concurrent
locale work; this step did not modify locale files.
