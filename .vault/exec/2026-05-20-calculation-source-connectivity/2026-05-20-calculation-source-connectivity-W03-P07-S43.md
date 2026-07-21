---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S43'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Test fincas and inventory resolvers emit blocked readiness diagnostics

## Scope

- `src/aeat/application/aggregation/test_source_mesh_readiness.py`

## Description

Add `application/aggregation/tests/test_source_mesh_readiness.py` (placed under `tests/` per the test-topology rule): the fail-closed proof that both readiness resolvers refuse visibly. It asserts each resolver emits exactly one `source_domain_not_ready` diagnostic (with the domain's `source_kind`, `resolver_id`, and `binding_source is None`) and resolves no value on any channel; that `fincas` / `inventory` are outside the `BindingSourceKind` taxonomy (so they cannot enter the enrolled/deferred/reserved source sets); that passing both through `merge_source_resolutions` adds no source and no value (only the two advisories); and that the live novel-source gate `assert_no_novel_source_kinds` stays green on a real revision.

## Outcome

The readiness contract is proven fail-closed and structurally non-enrolled. Landed in commit `7c15ee0184`. Verification: readiness test 6 passed; source-mesh enrollment/boundary suite 22 passed; ruff / ruff format / ty / pyright clean; `lint-imports` "Domain must not import application" KEPT; registry collect-only clean. Plan step W03.P07 S39-S43 marked complete.

## Notes

The test file was drafted by a peer unit during a coordinator handoff churn; it was retained verbatim because it encodes the exact resolver contract this build implements (no rework needed) and passes green against the landed modules. The build was placed under `tests/` rather than the plan's literal colocated path per the `tests-live-under-domain-tests-folders` rule.
