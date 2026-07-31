---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-07-17'
body_hash: 'sha256:0119a920866cb62139023dec118c0ed60426466c2275621d1e9a5d2006208f2d'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P03.S05` execution record

Extend `CasillaDefinition` and models with read-only `localized_labels` and `localized_help` dictionaries.

## Action

Modified `src/aeat/domain/calculations/registry/_schema_surfaces.py` to add:
- `localized_labels: dict[str, str] = Field(default_factory=dict)`
- `localized_help: dict[str, str] = Field(default_factory=dict)`
- Helper method `get_label(self, locale: str) -> str`
- Helper method `get_help(self, locale: str) -> str | None`

## Verification

Run pytest on the registry query and schema tests to ensure no regressions are introduced.
