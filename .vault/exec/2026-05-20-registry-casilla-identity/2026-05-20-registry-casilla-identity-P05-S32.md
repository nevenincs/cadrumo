---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S32'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-20-registry-casilla-identity-audit]]'
---

# `registry-casilla-identity` `P05.S32`

Implemented the legally grounded singleton `semantic_role` policy for
the typo-twin warning surface.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Updated: `.vault/plan/2026-05-20-registry-casilla-identity-plan.md`

## Description

The validator now records `legal_refs` and `source_refs` on each
semantic-role observation, then checks singleton warning candidates
against an explicit immutable policy table before emitting typo-twin
warnings. A policy match requires exact modelo id, revision id, casilla
id, semantic role, `legal_refs`, and `source_refs`; role names or role
prefixes alone cannot suppress a warning.

The policy covers the verified singleton pairs from the Step record:
Modelo 184 clave/subclave, Modelo 190 total percepciones
count/amount, Modelo 303 compensation anteriores/posteriores, the
Modelo 202 B2 tipo 3 and tipo 4 base/percentage slots plus the
Impuesto Complementario correction slot, and the current Modelo 369 OSS
destination-member-state services quota roles that were the live warning
noise.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_semantic_role.py` passes.

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py` passes: 35 tests.

`uv run pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py` passes: 25 tests.

`uv run pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress src/aeat/domain/calculations/registry/test_modelo_202_registry.py` passes: 4 tests.

`uv run pytest src/aeat/core/test_external_constants.py::test_live_safety_action_patterns_are_centralized -q` passes: 1 test.

`uv run pytest src/aeat/domain/calculations/registry` did not finish within the 5-minute command limit before producing actionable diagnostics.

Feature-surface gate:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_semantic_role.py` passes.
- `uv run --no-sync pytest -x src/aeat/domain/calculations/registry/test_semantic_role.py` passes: 35 tests.
- `uv run --no-sync vaultspec-core vault feature index -f registry-casilla-identity` refreshed `.vault/index/registry-casilla-identity.index.md`.
- `uv run --no-sync vaultspec-core vault check all --feature registry-casilla-identity` now reports `features: clean`, but still fails on vault-wide pre-existing structure filename violations.
