---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 Behaviour Gate Review

## Review Scope

- `registry/aeat/modelos/131.toml`
- `src/aeat/domain/calculations/registry/test_committed_registry.py`
- `src/aeat/domain/deadlines/test_engine.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Findings

- No blocking findings in the current Modelo 131 behaviour gate.
- The calculation test evaluates Modelo 131 through `build_snapshot` and
  `calculate_registry_snapshot`, and it caught the percentage-unit mismatch
  before the registry value was corrected to the shared `percent` operator
  convention.
- Deadline coverage now proves Modelo 131 is driven by the objective-estimation
  profile flag through the registry-backed deadline engine.
- Registry verification reports Modelo 131 as a validated current revision with
  calculation, extraction, static cross-reference, workbook-layout evidence,
  verification, application-link, and deadline surfaces.

## Residual Risk

- Historical Modelo 131 revisions 2019-2023, 2024, and 2025 remain open.
- Live filed-data discovery returned zero rows for the authenticated account, so
  no sanitized live fixture was committed for Modelo 131.
- Export roundtrip coverage remains open because the official Modelo 131 record
  design includes activity-detail pages that must be represented explicitly
  before export support is filing-grade.
