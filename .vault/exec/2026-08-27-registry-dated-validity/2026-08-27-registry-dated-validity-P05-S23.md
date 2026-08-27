---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f69b15a007c3495ee466a518565fea590c84323b6b77208e922ce37cbbf7a392'
step_id: 'S23'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Retire the fabricated home-office usage-ratio default so a suministro deduction requires the taxpayer's own declared proportion

## Scope

- `src/cadrumo/domain/usage_ratios/tests/test_model.py`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/categories/profiles.toml`
- `A` `src/cadrumo/domain/renta/tests/test_usage_ratio_requires_operator_input.py`
- `M` `src/cadrumo/domain/usage_ratios/tests/test_model.py`
- `verify:` `pytest domain/renta domain/usage_ratios domain/categories` -> `231 passed`
- `verify:` `pytest application/ledger/tests/test_preflight_home_office.py` -> `pass`
- `verify:` `bite proof reinstating default_ratio on one category` -> `both halves red, restore verified`

## Notes

Five categories carried `default_ratio = "0.30"` beside their real
`statutory_multiplier = "0.30"`. The evaluator reads `default_ratio` in the same slot
as a STORED ratio and stored ratios are already effective, because the censo derivation
multiplies the raw area proportion by the statutory factor before saving. So the
default asserted an EFFECTIVE thirty per cent, which LIRPF art. 30.2.5.b reaches only
at a raw afectacion of 1.00 -- the entire dwelling as office. A taxpayer who had
declared nothing deducted the maximum the article can ever allow.

The `statutory_multiplier` is deliberately kept: the 30 per cent IS statutory and the
censo derivation applies it. Only the fabricated second factor is gone, and a separate
assertion holds the multiplier in place so the correction cannot swing the other way.

The corrected documentation test in `domain/usage_ratios/tests/test_model.py` had
encoded the defect as the contract -- it called `default_ratio` "the statutory default"
and pinned a fallback pattern the article does not support.

32 tests are red in `application/ledger` and `adapters/persistence/profile` and NONE
are caused by this Step: they are `ConfirmationBlockedError` from the ledger
confirmation gate and stale composing-write declarations naming
`application/ledger/actions_common.py` and `application/workflow/_persistence.py`,
which trace to the peer commits `0e5e7ff94c` and `38a95dabdf`. No red involves category
profiles, usage ratios or deductibility.
