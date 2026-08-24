---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:108e3f6021850f4f23f48e2213d2a97a78929cb2d6eb4b3a5725a71861becb64'
step_id: 'S50'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Parameterize undeclared-grade refusal contradictions across every authority grade and prove weakened-guard regression refusal.

## Scope

- `src/cadrumo/application/registry/tests/`

## Description

- Replace the single applicability-only contradiction cases with dedicated parameterized direct-construction and revalidated-mutation tests over every `RegistryAuthorityGrade` member.
- Exercise an in-memory weakened copy of `_temporal_coverage.py` that rejects only applicability, then confirm direct and revalidated calculation and filing contradictions are admitted and the proof fails deliberately.
- Run focused Ruff and temporal-coverage pytest checks.

## Outcome

The all-non-null-grade contract is now explicit at both public construction paths. A guard weakened to the former applicability-only test shape admits calculation and filing contradictions on both paths, so the regression proof is specific to the full ladder property.

## Notes

`uv run --no-sync ruff check src/cadrumo/application/registry/tests/test_temporal_coverage.py` passed. `uv run --no-sync pytest -n 0 -q src/cadrumo/application/registry/tests/test_temporal_coverage.py` passed with 32 tests. The isolated in-memory weak-guard proof intentionally exited non-zero with `AssertionError`, listing direct and revalidated calculation and filing contradictions as admitted. No tracked production file was mutated.

