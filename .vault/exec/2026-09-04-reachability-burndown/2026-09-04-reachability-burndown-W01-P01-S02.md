---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:cfa4b5540a5f9687c3c80960ee7937762342220177de702a8ec44e749a87e24e'
step_id: 'S02'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Classify the 21 orphaned test modules against whether their shipped subjects are themselves findings

## Scope

- `src/cadrumo`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/audit/tests/test_reachability_classification.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`

## Notes

All 19 in-scope orphaned test modules are recorded; the remaining two are inside the
deferred TUI prefix.

The finding is structural and changes how this population should be treated. Every one of
the nineteen is DERIVATIVE: ten follow a module finding this campaign already classifies,
nine follow an unused symbol in a module that is otherwise reachable, and none has mixed
subjects. Not one is decided on its own terms.

The entries therefore record `follows` and `anchor` rather than a class from the taxonomy.
Every class in that taxonomy names an action, and none of these carries one. A test whose
subject is a `staged-capability` module is not dead code -- it is the proof that
capability still works, and deleting it would leave a staged module unguarded until its
dependency lands. A test following a symbol finding resolves when that symbol does.

The practical consequence is that this count cannot be burned down directly and must not
be treated as independent debt. It falls as its anchors resolve, and a test still reported
after its anchor is resolved is a real defect: a test that outlived its subject.

Corroboration for the previous Step's classification arrived here unprompted.
`domain.fincas.tests.test_imputacion_regime` exercises `cadrumo.domain.fincas.titularidad`
-- the exact module the accepted fincas titularidad decision is about -- so that staged
capability is demonstrably part-landed rather than abandoned.

Three gates added over the derivative entries: complete coverage against the live audit, a
valid `follows`/`anchor` pair on every entry, and a chain check that a module-following
test anchors to a module this ledger actually classifies, so the chain cannot dead-end.
Teeth proven for blank anchor, invalid `follows`, missing anchor, and a dangling chain.
