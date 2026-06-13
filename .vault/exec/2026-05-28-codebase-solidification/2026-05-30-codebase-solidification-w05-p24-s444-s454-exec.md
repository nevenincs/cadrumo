---
step_id: "S444"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P24.S444-S454 — A1 exception sweep

## Steps closed

S444, S445, S446, S447, S448, S449, S450, S451, S452, S453, S454

## New error classes (S444-S446)

- `WizardCatalogueNotRegisteredError(CoreError)` — code `INTERNAL_WIZARD_CATALOGUE_NOT_REGISTERED`
- `WizardCatalogueAlreadyRegisteredError(CoreError)` — code `INTERNAL_WIZARD_CATALOGUE_ALREADY_REGISTERED`
- `ProjectAnswersNotRegisteredError(CoreError)` — code `INTERNAL_PROFILE_PROJECT_ANSWERS_NOT_REGISTERED`

All three registered in `src/aeat/core/errors/registry/_core.py`. Locale keys added to en/es/ca/hu via `python -m aeat.locales set`.

## Narrowed except clauses (S447-S453)

| Site | Old | Narrow type |
|---|---|---|
| `modelo/_actions.py:2743` | `Exception` | `_decimal.InvalidOperation` |
| `user_profile/_profile_repository.py:308` | `Exception` | `(AeatError, OSError, ValidationError)` |
| `modelo/_result_summary.py:73` | `Exception` | `(LookupError, KeyError, AttributeError, AeatError)` + WARNING |
| `modelo/_result_summary.py:81` | `Exception` | `(LookupError, KeyError, AttributeError, AeatError)` + WARNING |
| `state_projection.py:357` | `Exception` | `(AeatError, OSError, ValueError, AttributeError)` |
| `state_projection.py:499` | `Exception` | `(AeatError, ValueError, LookupError, AttributeError)` |
| `live/__init__.py:1390` | `Exception` | `(_AeatError, OSError, asyncio.TimeoutError)` |
| `live/__init__.py:1419` | `Exception` | `(_AeatError, OSError, asyncio.TimeoutError)` |
| `live/__init__.py:1435` | `Exception` | `(_AeatError, OSError, asyncio.TimeoutError)` |
| `ledger/_actions.py:3439` | `Exception` | `(ValidationError, ValueError, KeyError)` |
| `ledger/_actions.py:3476` | `Exception` | `(AeatError, ValidationError)` |
| `review/_adapters.py:317` | `Exception` | `ImportError` |
| `review/_adapters.py:323` | `Exception` | `(AeatError, AttributeError)` |

## Aggregate test (S454)

`src/aeat/test_w05_p24_exceptions.py` — 21 assertions, all `unit + domain_core`.
Verifies registry codes, envelope roundtrip, and that non-typed exceptions propagate.

## Commit

`e08785f21` — core(errors): W05.P24 S444-S454 — A1 exception sweep

## Collision signal

Clean — no non-authored WIP on any target file at execution start.

## Locale audit

`python -m aeat.locales audit` → all 4 locales: ok
