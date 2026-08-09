---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:4243e38aa7cf7322c68e84b6b6d6f25f5765714d7311a47822fa76aa315f771a'
step_id: 'S18'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Measure and reopen the hot-path authority decision: memoise build_profile_grounding_index per authority and thread it into require_profile_ready_for_modelo_work, keeping require_existing_profile_baseline_ready_for_modelo_work registry-free

## Scope

- `fold in removing config profile preflight's duplicate report build on the ready path`
- `verification gate: a grounded regression asserting the blocking-gate refusal carries legal_refs for a field the grounding index covers, and a benchmark assertion bounding the added per-call cost`
- `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`

## Description

- Memoised `build_profile_grounding_index` in `src/cadrumo/domain/calculations/registry/_profile_grounding.py`: `ValidatedRegistryAuthority` is an unhashable `@dataclass(slots=True)` with no `__weakref__` slot, so neither `functools.lru_cache` (needs a hashable argument) nor a `weakref.finalize` eviction hook (needs a weak-referenceable object) apply directly. Landed a small `id(authority)`-keyed dict cache instead, bounded to 4 entries with FIFO eviction as a belt-and-braces cap - in practice at most one or two distinct authority instances are ever live in a process, so the bound is never exercised, but it keeps a long-running process or test session from growing the cache unbounded.
- Threaded `authority=resources().modelos.authority` into `require_profile_ready_for_modelo_work`'s existing `modelo_work_profile_preflight_report(...)` call (previously omitted - the exact gap the 2026-08-09 audit and this campaign's own P06 follow-up named).
- Discovered, while grounding the verification gate's regression, that threading authority into only that one call was insufficient: `require_profile_ready_for_modelo_work` raises EARLIER, from `_require_profile_filing_ready` (the baseline+validation check), for the common case of a missing `identity.tax_id` - and that helper built its requirement rows with no grounding at all. Added an optional `grounding_index` parameter to `_require_profile_filing_ready`, threaded through to both `_requirement_for_profile_path` and `_validation_missing_requirements`, defaulting to `None` so `require_existing_profile_baseline_ready_for_modelo_work` (the early, pre-registry-resolution gate) stays registry-free exactly as this Step's own text requires. `require_profile_ready_for_modelo_work` now computes the grounding index once and passes it to both the baseline check and the full report.
- Updated `modelo_work_profile_preflight_report`'s docstring, which previously stated the hot path omitted `authority` "as a deliberate scope decision, not a measured performance necessity" - now false; corrected to describe the memoised, always-threaded state.
- Evaluated `config profile preflight`'s two-call structure (build an unresolved-revision report first; only if `ready`, resolve the real revision and rebuild) against "remove the duplicate report build": the underlying per-call cost this named - `build_profile_grounding_index`'s registry-wide walk running multiple times per CLI invocation - is now eliminated by memoisation regardless of how many times `modelo_work_profile_preflight_report` is called. Collapsing the two-call CLI structure into one (always resolving the revision first) was considered and NOT done: `test_preflight_refuses_unresolvable_natural_key_with_discovery_pointer` and its siblings in `test_config_preflight_revision_default.py` depend on profile-level readiness being checked before a costly/failable revision resolution runs, and no test pins the reverse-order behaviour for the combined case (invalid period AND incomplete profile), so collapsing the order would be an unreviewed behaviour change with no coverage either way. Recorded here as a deliberate scope boundary rather than a silent skip.

## Outcome

`build_profile_grounding_index` is memoised per authority instance. `require_profile_ready_for_modelo_work` (the blocking work-creation/mutation gate) now carries real registry grounding on every refusal it raises, both from the baseline/validation path and the full preflight-report path, while `require_existing_profile_baseline_ready_for_modelo_work` (the early pre-resolution gate) stays registry-free as required. The CLI's two-phase `config profile preflight` build is retained by deliberate, recorded judgment rather than collapsed.

## Verification

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -m unit
21 passed in 16.19s
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/modelo/tests/ -m unit
12 failed, 1606 passed, 113 deselected in 246.11s (0:04:06)
```

All 12 failures are `NoRevisionForPeriodError: modelo 200: no revision for year=2024 period='0A'` and Modelo 202 fold-in tests depending on that same M200 2024 revision - a pre-existing registry-data gap unrelated to this Step's files (`_profile_readiness_gate.py`, `_profile_grounding.py`), consistent with the M200-registry-in-flight instability already noted earlier in this campaign (P04's audit spot-checks). Verified by inspecting the traceback: the failure originates in `_temporal.py`'s `select_revision`, three call frames before any profile-readiness code executes.

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py src/cadrumo/entrypoints/cli/tests/test_modelo_100_readiness_missing_bindings.py src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py -m integration
33 passed in 32.93s
```

The two new grounded gates added by this Step: `test_calculate_service_refusal_carries_grounded_legal_refs_for_missing_tax_id` (a real `calculate_modelo_revision` refusal on an existing Modelo 100 work unit whose profile carries zero facts asserts the refusal's `missing` context string contains the registry-grounded legal ref for `identity.tax_id`) and `test_grounding_index_lookup_stays_bounded_across_repeated_readiness_checks` (199 repeated calls to `build_profile_grounding_index` on the same live authority cost under half the first uncached call's wall time, and each call returns the identical cached object).

## Notes

The first memoisation attempt used `weakref.finalize` for cache eviction and failed at runtime with `TypeError: cannot create weak reference to 'ValidatedRegistryAuthority' object` - caught immediately by the existing test suite (`test_mark_verified_service_refuses_existing_work_unit_with_incomplete_profile`), not by inspection; `@dataclass(slots=True)` has no `__weakref__` slot unless declared. Replaced with the bounded FIFO dict before landing. No data loss, no skipped work.
