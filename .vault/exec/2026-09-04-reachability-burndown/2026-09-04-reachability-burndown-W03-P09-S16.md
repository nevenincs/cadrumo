---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:c7021465a1530c56ec864cef7b3f5011a6c58b53334b34b878fc8e513190f70a'
step_id: 'S16'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Merge the duplicated Decimal constants to a canonical home and repoint every call site, since a drifted numeric constant is a calculation defect

## Scope

- `src/cadrumo/core`

## Changes

- `A` `src/cadrumo/core/decimal/constants.py`
- `A` `src/cadrumo/core/decimal/tests/test_decimal_constants_are_canonical.py`
- `M` 36 modules repointed onto the canonical Decimal constants
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/notifications src/cadrumo/domain/contribuyente/inventory src/cadrumo/domain/prorrata_register` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry -k "formula_runtime or convenio or saturation or initial_values"` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/decimal/tests/test_decimal_constants_are_canonical.py` -> `pass`

## Notes

Thirty-six modules declared their own Decimal constants. They are now four canonical
definitions in `core/decimal/constants.py`, and the split between two of them is the
finding of this Step.

`_ZERO` meant TWO different values: `Decimal("0")` in twenty-two modules and
`Decimal("0.00")` in four. They compare equal, so no equality assertion anywhere would
have caught a module reaching the wrong one, but they carry different exponents and
Decimal arithmetic propagates the larger scale. Measured directly:
`str(Decimal("0") + Decimal("5"))` is `5` while `str(Decimal("0.00") + Decimal("5"))` is
`5.00`. Four modules depend on the two-decimal form, among them the sancion
`reducciones_total` sum that is returned for rendering and the inventory valuation whose
result reaches casillas 0177 and 0182. Merging all twenty-six into one constant would have
silently changed how amounts render on a filing surface.

They are therefore `ZERO` and `MONEY_ZERO`, named for the distinction rather than the
number, and the gate asserts the exponents stay different.

## Notes on the gate

The first gate flagged eleven further modules, and only six were duplicates. The others
hold the same NUMBER under a name that states a domain rule: `PERCENTAGE_MAX` and
`UNIT_PROPORTION_MAX` are declared bounds on their types, `_MAX_IVA_RATE_FRACTION` bounds
a rate, `_FULL_PERCENTAGE` and `_FULL_BUSINESS_PROPORTION` name a whole share. Merging
those would tie a domain rule to an arithmetic constant.

The gate now keys on whether the NAME describes the number rather than a concept, which is
the same distinction this module's own docstring draws between `HUNDRED` and
`PERCENTAGE_MAX`. Six value-named constants were migrated as a result: `_ONE_HUNDRED`,
`_PERCENT`, `_PCT_SCALE`, and three `_ZERO` sites the name-based migrator missed because
they were annotated `Final` rather than `Final[Decimal]`.

Teeth proven by reintroducing a local `_HUNDRED`: the gate exits 1 naming the module, and
exits 0 once restored.

Unrelated failures observed and left alone: six `F822` undefined-name entries in
`application/filing/producer_snapshot.py` `__all__`, last touched by peer commit
eff7ce61f3, and one ty diagnostic in the TUI ledger. Neither module imports these
constants.
