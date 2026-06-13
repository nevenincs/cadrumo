---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Wave 6` `Modelo 180 annual-summary core`

Expanded Modelo 180 from source-grounded identity into a registry-backed
annual-summary core for the official fixed-width record design.

- Modified: `registry/aeat/modelos/180.toml`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Modelo 180 now declares the core declarante annual summary fields and perceptor
monetary record fields for both supported revisions. The definition adds
Modelo 115 annual-summary relations, target bindings, relation-backed formulas,
official record-layout slices, submitted-file extraction profiles,
verification expectations, and application links through the central registry.

The filing runtime now omits modelos that are not applicable to an explicitly
requested year/period, so quarterly providers are not blocked by annual-only
modelos. The export renderer now preserves the official signed-money sign slot:
positive signed values render with a blank prefix and negative values keep the
`N` prefix.

## Tests

- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_export.py -q`
- `uv run ruff check src\aeat\application\filing\runtime.py src\aeat\application\filing\_export.py src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\test_committed_registry.py registry\aeat\modelos\180.toml`
- `uv run ty check src\aeat\application\filing\runtime.py src\aeat\application\filing\_export.py src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\test_committed_registry.py`
