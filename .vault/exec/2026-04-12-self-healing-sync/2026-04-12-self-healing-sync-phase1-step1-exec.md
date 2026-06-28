---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 1 — errors, protocols, wire schemas

Scaffolded `src/aeat/application/sync/` with:

- `_errors.py` — `SyncError` + `WireValidationError`,
  `DivergenceClassificationError`, `HealingError`,
  `DivergenceRepositoryError`.
- `_protocols.py` — rebase-swap Protocols for #6, #7, #8, #9, #10,
  #17, #21, #25. `ModeloIdentifier` / `PortalIdentifier` are typed
  string validators with pydantic core schema hooks.
- `_wire.py` — strict frozen pydantic v2 models:
  `WireCasilla`, `WireModeloDefinition`, `WireFilingEntry`,
  `WireFilingHistory`, `WirePortalLink`, `WirePortalManifest`.
- `_validator.py` — `WireValidator.validate` wrapping
  `model_validate_json` into `WireValidationError`.
- `test_wire.py` — round-trip + rejection cases for each schema.

Public `__init__.py` re-exports the step-1 surface.
