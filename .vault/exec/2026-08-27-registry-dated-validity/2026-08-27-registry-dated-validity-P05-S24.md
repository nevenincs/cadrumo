---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:858f4ef6e0e6d999a875bb164ca345efc7dde126e1db070eb0d726d0f5ddb7f3'
step_id: 'S24'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Carry the censo-declared dwelling area into the deduction and centralise the home-office grouping

## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Changes

- `A` `src/cadrumo/application/user_profile/usage_ratio_resolution.py`
- `M` `src/cadrumo/application/user_profile/censo_sync.py`
- `A` `src/cadrumo/application/user_profile/tests/test_usage_ratio_resolution.py`
- `M` `src/cadrumo/domain/categories/_spending_category.py`
- `M` `src/cadrumo/domain/categories/__init__.py`
- `A` `src/cadrumo/domain/categories/tests/test_home_office_grouping_is_centralised.py`
- `M` `src/cadrumo/domain/usage_ratios/_service.py`
- `M` `src/cadrumo/adapters/persistence/profile/usage_ratios.py`
- `M` `src/cadrumo/application/ledger/preflight.py`
- `M` `src/cadrumo/application/ledger/ratios.py`
- `M` `src/cadrumo/application/state_projection.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `verify:` `pytest domain/categories domain/usage_ratios domain/renta application/aggregation + preflight + resolver` -> `1301 passed, 5 failed (peer)`
- `verify:` `bite proof: un-wire the derivation` -> `red, restore verified`
- `verify:` `bite proof: reinstate a local family grouping` -> `red on the gate's own assertion, restore verified`

## Notes

The censo 036 declaration reached the deduction only as a VALIDATOR before this Step.
`CensoSyncService.bound_raw_afectacion_ratio` computed office_m2/total_m2 and
`derive_home_office_ratios_from_censo` applied the art. 30.2.5.b thirty per cent, but
no production caller joined them: the operator had to retype the ratio through
`ledger ratios set`, and a filer who declared their m2 and never did deducted nothing
on utilities, silently, with no preflight reason for it. The calculate path now resolves
ratios through `resolve_effective_usage_ratios`, and a new
`MISSING_HOME_OFFICE_AFECTACION` preflight reason reports the case where neither a
stored ratio nor censo m2 exist.

Deriving is not new policy: the censo guard already refuses any stored home-office
ratio that is not exactly the derived one and blocks calculation on mismatch, so the
stored value carried no information the censo did not already have.

Centralisation, which is the larger half of this Step. `_HOME_OFFICE_FAMILIES` was
declared FOUR times -- `domain/usage_ratios/_service.py`,
`adapters/persistence/profile/usage_ratios.py`, `application/ledger/ratios.py`,
`application/ledger/preflight.py` -- two as tuples and two as frozensets, and two of
those modules also each carried their own `_home_office_categories()`. A fifth copy was
added and removed within this Step. All are deleted; `HOME_OFFICE_FAMILIES` and
`home_office_categories()` now live once in `domain/categories/_spending_category.py`
beside the membership table they derive from, with every consumer importing them. No
shim, no re-export, no alias. The identical `CensoSyncService(bucket_id=X)
.bound_raw_afectacion_ratio(profile_id=X)` call, restated at two production sites, is
now `bound_raw_afectacion_ratio_for_bucket`; the CLI listing is deliberately NOT folded
in, because it resolves a profile_id that can differ from the bucket.

A gate holds the centralisation: a module that references both family members in code
reds. It reads the AST rather than the raw text, because several modules legitimately
explain the difference between the two families in prose -- the first version of the
gate flagged two such docstrings, which is how that distinction was found.

Five aggregation tests are red and none are caused by this Step: an m210 `pais`
row-model validator raising on None, an IVA source-mesh authority test, an atribucion
required-set test and a cross-modelo invoice period test. The same five were red before
this Step's first edit, and all sit in peer paths.
