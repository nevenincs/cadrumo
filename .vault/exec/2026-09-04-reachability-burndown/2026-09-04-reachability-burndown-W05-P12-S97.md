---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:fc340b29f202608cc4fccd1c073df8f98060ea667d636c20b12f948ddcafb532'
step_id: 'S97'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Re-verify every open ledger claim with the alias-aware counting the previous step's bug exposed, finding none contradicted, then close the silence around the sectoral prorrata regime: the general and especial regimes of that substrate are computed by the live path and the differentiated-sectors one is not, so a taxpayer whose activities do form distinct sectors deducts without the separation art. 9.1.c requires. Wiring it stays a filing-grade capability decision; the module now says which of its regimes is reached, because everything around the sectoral path is.

## Scope

- `src/cadrumo/domain/iva/prorrata.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/domain/iva/prorrata.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest src/cadrumo/domain/iva/tests/` 841 passed
- `verify:` the four ledger gates 25 passed; `docstring_reference_ratchet`,
  module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` `ruff check` and `ty check` clean

## Notes

The integrity check came first, because the aliased-import bug found last step
is exactly the kind that corrupts a "no caller" claim. Every open ledger symbol
was re-counted with alias-aware resolution, recording both halves of every
import: none has a production reference outside its own module. The ledger's
claims survive the bug that could have invalidated them.

The sectoral prorrata cluster is confirmed, not reversed, and the shape is worth
naming. Its module is MAJORITY LIVE -- six of its public functions are reached
by the calculation path -- and only the differentiated-sectors regime is not. A
reader of a module that is mostly wired has no way to tell which part is not,
and the consequence here is a deduction: a taxpayer whose activities form
distinct sectors deducts without the separation art. 9.1.c requires.

So the art. 9.1.c paragraph now says the sectoral regime is declared and not yet
reached. Wiring it is a filing-grade capability decision and stays open, and
that is the fourth time the wiring question and the truth of the claim have come
apart in this campaign with the second half fixable immediately.

A partially-live module is a worse place for an unreached path than a fully dead
one, because the surrounding evidence argues against the reader noticing.
