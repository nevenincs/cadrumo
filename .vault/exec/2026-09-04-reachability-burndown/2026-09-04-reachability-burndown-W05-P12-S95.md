---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b42c1291e325db02bda52a7feed007ed17d22510e6ec5e35df65f2380c055427'
step_id: 'S95'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Check whether the wrong-derivation error that produced a false structural claim recurs elsewhere, finding no open cluster still makes one, then close the silence around the art-108 escaso-valor threshold: the figure sits among enforced thresholds in the external constants with nothing saying it is not one, while the bienes-de-inversion register takes eligibility as an operator boolean and stores no acquisition value to compare. Whether the product should judge art. 108 stays an owner decision; the constant now states that it is declared and not yet applied.

## Scope

- `src/cadrumo/core/external_constants.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/core/external_constants.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest src/cadrumo/core/tests/test_external_constants.py` 23 passed;
  `dev/quality/tests/test_cited_constants_are_protected.py` 4 passed
- `verify:` the three ledger gates 19 passed; `docstring_reference_ratchet`,
  module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` `ruff check` and `ty check` clean

## Notes

The recurrence check was quick and negative: no open cluster still makes a
structural-absence claim, so the `vars`-only derivation that produced the false
"no implementer" entry has no other victim in the ledger.

The escaso-valor threshold is a genuine owner decision and stays open. The
register takes `art108_elegible` as an operator-supplied boolean and stores
`cuota_soportada` rather than an acquisition value, so there is nothing to
compare the figure against; applying it means a schema change AND a ruling on
whether the product judges art. 108 or the operator does.

What did not have to wait on that ruling is the silence. The constant sat in
`external_constants.py` among thresholds that ARE enforced, with nothing
distinguishing it, and a legally grounded figure in that file reads as applied.
A reader had no way to learn otherwise short of grepping for callers. Its
comment now says it is declared and not yet applied, and why.

That is the third time this split has paid: the wiring question and the truth of
the claim are separable, and the second half is almost always fixable now. Here
it matters more than usual, because the claim is about tax law -- the file's
whole purpose is to be the place a reader trusts for what the product applies.
