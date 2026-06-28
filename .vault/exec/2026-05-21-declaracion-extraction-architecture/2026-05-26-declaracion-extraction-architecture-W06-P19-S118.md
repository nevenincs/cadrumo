---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S118'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S118

Added shared-model boundary guards for declaration extraction.

- Created: `src/aeat/adapters/inbound/declaracion/test_shared_model_boundaries.py`

## Description

Added tests proving declaration extraction exposes strict pydantic boundary
records and reuses the shared PDF and registry models instead of duplicating
local shapes:

- `DeclaracionObservation`, `ExtractionWarning`, and `TemplateRevision` are
  pydantic models.
- `DeclaracionObservation.values` is typed as shared
  `ExtractedCasilla` records.
- `DeclaracionObservation.registry_snapshot_ref` is typed as the shared
  registry `RegistrySnapshotRef`.

## Tests

- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\test_shared_model_boundaries.py`
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_shared_model_boundaries.py -q`
