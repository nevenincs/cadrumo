---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S438'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S438`

## Description

- Tracks the Modelo 202 1P quota-base previous-year source-coverage gap discovered while unblocking calc-sheets validation.
- Requires either modelling the needed Modelo 200 historical source coverage or adding an explicit registry gate so the 1P legal hook is not left as comment-only operator-manual behavior.
- Keeps the issue separate from S435 so the 2P/3P registry fix can remain closed without claiming 1P is production-ready.
- Add a repository-backed application test proving Modelo 202 1P resolves its cuota-base from the target year minus two, while a nearer target year minus one Modelo 200 observation is present and ignored.
- Add committed registry assertions that the 1P and 2P/3P cuota-base relations are both present in the Modelo 202 foundation construct, with the expected source output, target binding, target periods, source periods, and filing-year deltas.
- Refresh the Modelo 202 continuity test wording so 1P is no longer described as deferred/operator-only behavior.

## Outcome

Closed.

The S438 gap is now executable coverage rather than comment-only registry intent. The 1P gate uses real `CalculationObservationRepository` observations, the real registry snapshot, and the real relation-prefill resolver; it does not use fakes, mocks, monkeypatching, skips, or xfail.

Verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/application/calculations/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py` -> 8 passed.
- `uv run --no-sync pytest -q src/aeat/application/calculations/test_relation_prefill_source_mesh.py` -> 3 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/application/calculations/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py` -> all checks passed.

## Notes

No HIGH or CRITICAL issue was identified while closing this slice.
