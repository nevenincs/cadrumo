---
step_id: S43
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P01.S43 - introduce AggregationConfigError

## Outcome

Introduced `AggregationConfigError(CoreError, ValueError)` in
`src/aeat/application/aggregation/_errors.py`. Replaced all 9 bare `ValueError`
raises in `src/aeat/application/aggregation/_service.py` service-composition
validators with `AggregationConfigError`.

## Files touched

- `src/aeat/application/aggregation/_errors.py` — new class `AggregationConfigError`; added to `__all__`
- `src/aeat/application/aggregation/_service.py` — import `AggregationConfigError`; 9 raises migrated
- `src/aeat/application/aggregation/__init__.py` — export `AggregationConfigError`
- `src/aeat/core/errors/registry/_application.py` — `ERROR_AGGREGATION_CONFIG` entry (pre-landed by S27/S28 campaign)
- `src/aeat/locales/{en,es,ca,hu}.yml` — `errors.error.error_aggregation_config` key (pre-landed by S27/S28 campaign)

## Raises migrated (9 sites)

1. `PerModeloAggregationProviderContract._modelos_are_unique` — "provider modelos must be unique"
2. `PerModeloAggregationContract._providers_are_unique` — "per-modelo aggregation providers must be unique"
3. `PerModeloAggregationContract._providers_are_unique` — "per-modelo aggregation modelos must be owned by exactly one provider"
4. `PerModeloAggregationContract._source_kinds_are_exact` — "source kinds must match the accepted four-kind taxonomy"
5. `PerModeloAggregationCommand._only_matching_observation_family_is_populated` — cross-family observations
6. `PerModeloAggregationResult._source_kinds_are_unique` — "result source_kinds must be unique"
7. `PerModeloAggregationResult._envelope_matches_payload` — modelo mismatch
8. `PerModeloAggregationResult._envelope_matches_payload` — period mismatch
9. `PerModeloAggregationResult._envelope_matches_payload` — provider/payload type mismatch

## Design notes

`AggregationConfigError` inherits from both `CoreError` and `ValueError` so
pydantic field/model validators surface it through `ValidationError` without
special handling. Existing tests in `test_per_modelo_service.py` that assert
`pytest.raises(ValidationError, ...)` continue to pass.

## Commit SHA

`e3cf65e5d`
