---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ad15497051707a3aa7ad714e7b050f04a53c68e0cfa79290afac463713194b51'
step_id: 'S44'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# Acquire and hash-pin exact official Modelo 182 design eras and amendment authority

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/182/`
- `src/cadrumo/_data/registry/aeat/legal/modelo-182.toml`
- `src/cadrumo/domain/calculations/registry/tests/test_legal_review_authority_scope.py`

## Description

- Confirm the exact 2025 AEAT record design remains the sole selected M182 design era, with the canonical HAC/1430/2025 amendment and first-application authority; the 2024 design remains hash-pinned catalogue evidence but is not selected.
- Reconcile the public authority-scope proof with the live legal catalogue: four legacy legal refs are operator-reviewed, while HAC/1430/2025 article 2 and final provision are agent-reviewed.
- Prove neither reviewed-reference category promotes M182's agent-reviewed applicability-grade revision. The public accessor continues to refuse it at the authority-grade boundary; the pending-review and agent-review mutations retain their distinct refusal paths.

## Outcome

Modelo 182 remains one `2025` applicability-grade revision with no export layout or filing promotion. Its exact source applies only to 2025, while 2007-2024 and 2026 onward remain unsupported. The legal-review test now fails on a changed legacy/amendment review partition instead of falsely requiring all six refs to be operator-reviewed.

## Verification

- `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_legal_review_authority_scope.py` - 6 passed.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_modelo_182_temporal_grounding.py src/cadrumo/domain/calculations/registry/tests/test_record_design.py -k '182 or modelo_182'` - 2 passed, 81 deselected.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py::test_committed_registry_tree_has_coherent_shared_catalogues` - 1 passed.
- Scoped Ruff format, Ruff check, and diff check passed.

## Notes

- Agent-reviewed legal amendment evidence is not a filing-authority upgrade. No registry data change was necessary.
