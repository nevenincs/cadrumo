---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:e027694f2b1aa70e15a339d09c5fff6f10b1290b3bb4ca73d5508a346602bb64'
step_id: 'S08'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Resolve the domain/calculations exact-confidence symbol concentration at its owning boundary

## Scope

- `src/cadrumo/domain/calculations`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `M` five registry data-type test modules repointed at the canonical implementation
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests -k "data_type or scalar or schema"` -> `3 pre-existing failures, 364 passed`

## Notes

A two-layer alias chain, and the second layer was only visible after the first was
removed.

`schema_scalars` defined each validator privately, used the private name in its own
`Annotated` type, and bound a PUBLIC alias to it. `schema.py` imported that public alias
under an `_impl` name and bound a second private alias, so tests could import the validator
from `schema`. Neither layer had a production consumer: each `_impl` appeared exactly twice
in `schema.py` -- its import and its alias -- and the public aliases carried a comment
stating they existed to let the schema facade preserve its historical private names.

Removing the outer layer made the count go UP by one rather than down by five, which is
what exposed the inner layer: the public aliases lost their only consumer and became
findings themselves. Both layers are now gone, tests import the private implementation
directly, and `schema_scalars` reports zero exact findings where it previously reported
five. The tree-wide count moved from 1391 to 1387.

One near-miss worth recording. `validate_country_code` appeared to have seven consumers,
which would have blocked its removal. Checking the import SOURCE rather than the name
showed every one of them resolves to `domain.invoices.validators.validate_country_code` --
a different function that happens to share the name. That is the same rule the test-only
triage Step had to adopt, and the second time in this campaign that a name match alone
would have produced the wrong answer.

Three failures in the registry schema suite are pre-existing, proven by A/B against copies
of both unmodified modules and the five unmodified tests: 3 failed and 364 passed
identically with and without this change.

## Notes on remaining scope

This Step's area is not exhausted. 96 exact findings remain in `domain/calculations`, and
sampling showed two further classes rather than one: `live_parity` and
`record_design_coverage` are parity and coverage harnesses whose consumers are `dev` and
tests, which is the design-time-authority shape already adjudicated for the operator
surface, and `authority.py` mixes a dev-only inspection entry point with a test-only cache
reset. Those need their own passes.
