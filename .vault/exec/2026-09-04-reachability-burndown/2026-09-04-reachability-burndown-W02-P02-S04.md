---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:84d8a9d0fe056a4dda090a1fbf5a644551d616cb5e9accf41cc1ccbef50e6769'
step_id: 'S04'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Relocate dev-only harness modules beside their dev consumers and shrink the ratchet by the entries resolved

## Scope

- `dev`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/audit/tests/test_reachability_classification.py`
- `M` `.vault/adr/2026-09-04-reachability-burndown-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`

## Notes

Nothing was relocated, and that is the result. Attempting this Step's remedy disproved the
classification it depended on.

All four modules recorded as `harness-code` are product declarations. `crud_registry` is
the locked CRUD design for the operator CLI and `crud_contract` the verb vocabulary it
instantiates; no entrypoints module uses `CrudVerb`, `CANONICAL_CRUD_VERBS` or
`get_builtin_catalogue`, and the reader is a drift gate checking shipped Typer subgroups
against the declared design. `calculation_workflows` is a pydantic contract over the
operator-surface reconciliation. `record_spec` names itself the single authoritative home
for constants governing how registry record declarations are validated, placed there to
avoid a circular import.

Relocating any of them into `dev/` would have moved the product's own design out of the
product, and for `record_spec` would have moved filing-grade registry constants out of the
registry authority.

The class already existed in the tree without a name: `cadrumo.core.address_components`
carries `design_time_authority` in the module ratchet for exactly this shape -- a
declaration constraining other declarations, with no runtime caller by design. The
taxonomy now names it, the ledger reclassifies the four, the gate's closed vocabulary
accepts it, and the governing decision carries an amendment recording why the original
single `harness-code` class conflated two different things.

The generalisable lesson is recorded in the reference: who reads a module does not
establish what it is, and a classification is only safe once its remedy has been attempted
against the tree. A relocation done on the first reading would have been a regression that
every gate here would have passed.

## Notes on plan revision

`W02.P02` has no remaining subjects, since its population was the four now reclassified.
A Step was added through the plan verbs to record the design-time authorities as
`[[intentional]]` in the module ratchet with their conformance-gate reader named, which is
the remedy the corrected class dictates.
