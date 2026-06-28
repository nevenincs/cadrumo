---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 123 Extraction And Export Behaviour Review

## Review Scope

- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
- `src/aeat/application/filing/test_export.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Findings

- No blocking findings in the focused parser/export patch.
- Modelo 123 current 2026 declaration extraction now exercises the
  registry-selected declaration PDF profile through `parse_declaracion`.
- Modelo 123 2019-2023 declaration extraction now exercises the historical
  registry-selected declaration PDF profile through `parse_declaracion`.
- Modelo 123 2019-2023 exported records now round-trip through `verify_export`
  against the same runtime registry snapshot used to build the draft.
- Registry verification passes with Modelo 123 revisions `2019-2023` and
  `2024-y-siguientes`, each exposing one export layout and one declaration
  extraction profile.

## Residual Risk

- A committed sanitized live declaration-copy fixture is still pending in the
  Modelo 123 plan ledger.
