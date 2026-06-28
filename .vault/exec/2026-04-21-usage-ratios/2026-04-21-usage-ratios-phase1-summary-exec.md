---
tags:
  - "#exec"
  - "#usage-ratios"
date: 2026-04-21
modified: '2026-04-21'
related:
  - "[[2026-04-21-usage-ratios-plan]]"
  - "[[2026-04-21-usage-ratios-adr]]"
  - "[[2026-04-21-usage-ratios-research]]"
  - "[[2026-04-21-usage-ratios-code-review-exec]]"
---

# 2026-04-21-usage-ratios-phase1-summary

## Summary

The #259 feature — Kent persists his own per-category usage-ratio coefficients — is implemented and shipped on `feature/259-usage-ratios`. The initial implementation (commit `f0f781d`) was followed by four rolling audit rounds that surfaced and closed 19 discrete findings without introducing any critical regressions. PR #306 is open against `main`.

## Shipped package layout

```
src/aeat/domain/financial/usage_ratios/
├── __init__.py                 # public API (7 names)
├── _errors.py                  # UsageRatioError + UsageRatioPersistenceError
├── _model.py                   # UsageRatioProfile, ELIGIBLE_USAGE_RATIO_CATEGORIES, resolve_user_ratio
├── _service.py                 # load_usage_ratios, save_usage_ratios (atomic, BOM-tolerant)
├── test_model.py
└── test_service.py

src/aeat/entrypoints/cli/financial/
├── profile.py                  # `aeat financial profile` Typer surface
├── _profile_aliases.py         # CLI-private FAMILY_ALIASES (disjoint, ratio-stable)
├── test_profile.py
└── test_profile_aliases.py
```

Settings field `aeat_usage_ratios_path` in `src/aeat/config.py`; default `var/financial/usage-ratios.json`. Documented in `env/.env.example`.

## Commit trajectory

| Commit | Round | Focus |
|---|---|---|
| `f0f781d` | — | Baseline: model + service + CLI + tests (44 tests) |
| `9b51c78` | R1 | Dropped dead `is_finite` in model; canonical key ordering on save; strengthened tautological tests; added edge-case coverage |
| `437dab7` | R2 | Moved `FAMILY_ALIASES` to CLI-private; dropped `phone_fixed_business` (alias overlap); surfaced pydantic / OSError detail; extended unknown-key hint with `difflib` near-matches; ADR amendments |
| `dce6eed` | R3-regression | Derived Typer help from `FAMILY_ALIASES` (fix for stale alias in help); UTF-8 BOM tolerance; rewrote tautological mutation test |
| `6354eea` | R3-UX | Substituted pydantic's 38-entry enum dump with focused 12-category list; `_indented_wrap` wrapping; trailing-space tolerance; unified ineligible-category branch |
| `231424f` | R4 | Trailing-newline + `newline="\n"` on persisted JSON; import hoist; `_indented_wrap` empty-items guard; six atomicity / silent-swallow / zero-format blindspot pins |

## Test and coverage footprint

- 70 tests total (44 baseline + 26 added across rounds).
- 100% coverage on `src/aeat/domain/financial/usage_ratios/`.
- ≥ 93% coverage on `src/aeat/entrypoints/cli/financial/profile.py` + `_profile_aliases.py`.
- Zero mocks, zero patches, zero stubs (pytest-only mandate honoured).
- All tests are Rust-style colocated; module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]`.

## Consumer contracts locked in

- **`resolve_user_ratio(profile, category) -> Decimal | None`** — pure, O(1), returns `None` for unset or ineligible categories. Issue #257's deductibility compute will call this before falling back to `ProportionalityRule.default_ratio`.
- **`UsageRatioProfile`** — frozen pydantic v2 model, `extra="forbid"`, ratios bounded to `[0, 1]`, canonical `SpendingCategory.value` ordering on save, UTF-8 with a trailing LF, atomic via `NamedTemporaryFile` + `os.replace`.
- **12 eligible categories** (`USAGE_RATIO_HOME_AREA` ∪ `USAGE_RATIO_PERSONAL`) exposed as `ELIGIBLE_USAGE_RATIO_CATEGORIES`.
- **Two disjoint CLI aliases** (`home_office_area`, `mileage_business`) — CLI-private, never persisted. Overlap explicitly rejected by `test_no_alias_overlap_across_the_mapping`.

## Deferred work

- **Concurrent-writer data loss** → [issue #310](https://github.com/wgergely/aeat/issues/310). The ADR originally documented this as "last writer wins", but the rolling audit showed whole keys can vanish under parallel `set-ratio` invocations. Not in scope for #259; will block #214 (setup wizard) work if Kent scripts parallel sets.
- **Multi-year registries** — `ELIGIBLE_USAGE_RATIO_CATEGORIES` is derived from `CATEGORY_PROFILES_2025` at module load. A future multi-year refactor must re-derive per-year.
- **i18n wiring** — the entire `src/aeat/entrypoints/cli/` tree is English-only; `AEAT_OUTPUT_LANGUAGE` has zero readers project-wide. #259 matches the sibling convention. A dedicated EPIC should localise the CLI layer as a coordinated effort.
- **Shared atomic-save helper** — `save_usage_ratios` mirrors `invoices/_service.py` and `transactions/_service.py`. Three near-identical implementations; extraction was below the threshold for #259 and deliberately declined by the ADR.

## Next Steps

Proceed to the mandatory code-review phase (`2026-04-21-usage-ratios-code-review-exec`) and merge PR #306 once all green.
