---
tags:
  - '#exec'
  - '#adr-amendment-implementing-rows'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:be083a16c9c4247f9b23aa64257b4898e947cefbe8ae330bceec9b5431f837ba'
step_id: 'S05'
related:
  - "[[2026-08-07-adr-amendment-implementing-rows-plan]]"
---
# `adr-amendment-implementing-rows` execution: `S05`

## Description

- Record the already-landed applied-rate-and-date lookup from commit `d43bd3366a5948e59e3fd2bab5462a2550e070fc`.
- Store the Article 161 recargo rate table as windowed `applied_rate` evidence, including the transitional rates that make a rate-tier-only lookup ambiguous.
- Expose the applied-rate lookup through the IVA facade and reject overlapping windows for one rate at registry load.
- Preserve the legacy rate-tier helper while production consumers migrate to the unambiguous applied-rate lookup.

## Outcome

The committed lookup answers recargo equivalencia from the IVA rate a line actually carried and its effective date. It returns no answer for an unmodelled rate/date pair rather than selecting an adjacent or ambiguous tier. This is the completed precondition for S04's non-blocking mismatch advisory.

## Verification

`git merge-base --is-ancestor d43bd3366a HEAD`

`S05_ANCESTOR_OF_HEAD=yes`

`git merge-base --is-ancestor d43bd3366a origin/main`

`S05_ANCESTOR_OF_ORIGIN_MAIN=yes`

`uv run --no-sync pytest -n 0 -q src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py src/cadrumo/domain/iva/tests/test_iva_registry_grounding.py src/cadrumo/application/aggregation/tests/test_recargo_rate_advisory.py src/cadrumo/domain/iva/tests/test_recargo_equivalencia.py`

`33 passed in 3.85s`

`uv run --no-sync ruff check src/cadrumo/domain/iva/__init__.py src/cadrumo/domain/iva/_recargo_equivalencia.py src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/domain/iva/__init__.py src/cadrumo/domain/iva/_recargo_equivalencia.py src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py`

`0 errors, 0 warnings, 0 notes`

## Notes

This is a truthful historical execution record. It adds no production change: the four implementation files were introduced by the recorded commit. The accepted coordination ADR now authorizes an execution record under this plan feature, resolving the prior execution-mapping gap without changing S05's implementation scope.
