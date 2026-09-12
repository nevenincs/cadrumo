---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:f7b33a1f52201e4a2deb77cc38afd534c0f845c87b38665496f89db610967b3e'
step_id: 'S14'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Run registry verify, owning tests and import-boundary gates; record outcomes

## Scope

- `dev/registry/tests/`
- `src/cadrumo/domain/calculations/registry/tests/`
- `src/cadrumo/application/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_value_contract.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_terminal_origin.py`
- `A` `dev/registry/fix_binding_row_set_contracts.py`
- `A` `dev/registry/tests/test_fix_binding_row_set_contracts.py`
- `A` `dev/registry/tests/test_binding_registration_corpus_gate.py`
- `M` `dev/registry/convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_convert_binding_provider_shape.py`
- `M` `justfile`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_binding_registration_corpus_gate.py -n 0` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_convert_binding_provider_shape.py dev/registry/tests/test_fix_binding_row_set_contracts.py -n 0` -> `pass`
- `verify:` `uv run --no-sync ty check` on the touched modules -> `pass`

## Notes

The corpus rewrite this Step provisioned was already applied by a concurrent
writer: `fix_binding_row_set_contracts --all --dry-run` reports 336 of 336
row-producing rows already on the row-set shape and zero rewrites pending, so
the tool ran as a verified no-op and no registry data file was written. The
before/after hash comparison of all 774 authored binding fragments shows zero
changes.

The registry test suites cannot run under `pytest` in this tree: a session
fixture loads the bundled authority artifact, which is stale against the
current schema (`casilla_continuidad_evolutions` is no longer an enrolled
family) and fails collection for 63 unrelated tests. The domain tests for this
Step were therefore verified by direct execution instead, 93 passing across the
value-contract, registration, and terminal-origin modules.

### Test-lane migration after the binding-schema cut

A follow-on pass migrated the test corpus onto the post-cut provider API and
re-measured the owning lanes. Only test modules and test-support helpers were
edited; no production module, registry data file, or generated artifact was
touched.

Collection blockers cleared (4 modules): the previous-filing offset test was
rebuilt on a `PreviousFilingProvider` carrying a `TargetPeriodOffset`; the query
test moved from the retired relation grouping to
`relation_prefill_bindings_for_period`; both copies of the ahorro-base chain
moved from the deleted `relation_aggregation` module to `binding_aggregation_op`.

Identifier migration was corpus-verified rather than pattern-applied. Three
mechanical passes ran, each checking every produced identifier against the
declared corpus before writing: 110 edition-collapsed ids across 79 files, the
72-entry relation-to-binding join map across 96 files, and 5 residual
`m210`/`modelo-200` collapses across 24 files. Interpolated ids built by
f-string were de-interpolated only where the collapsed form existed AND no
edition-keyed variant survived; the one case that failed that second test
(`renta-{year}-dependent-modelos`, still edition-keyed on the 2020-2024
revisions) was kept interpolated. An AST pass then removed 33 duplicate dict and
set entries created where two relation ids merged onto one binding; every
duplicate was value-identical, so no fixture value was silently dropped.

Two assertions were retargeted because their subject no longer exists. The
query row test asserted a `typed_enum` binding consumed on the decimal channel;
no such declaration remains (the estimación-directa binding is boolean now, and
every surviving `typed_enum` is enum-channel), so it now asserts that the row
surfaces the declared `typed_enum` at all. The standalone relation schema-record
family is gone from the workspace surface — a fold's endpoints now hang off the
casilla and binding records — so its dedicated test was deleted and the parity
block dropped; the two surviving endpoint tests already cover each side.

One test module deletion and no other removals. Sources of residual failure are
recorded below.

Lane measurements, taken before the tree became unimportable:

- registry domain: 181 failed, 2158 passed, 3 errors
- application calculations: 168 failed, 500 passed, 4 errors
- application aggregation: 381 failed, 658 passed, 2 errors
- application modelo: not measurable; its `conftest` import fails
- dev registry: not measurable; see below

Comparison against a detached HEAD worktree shows the tree improving rather than
regressing: registry domain went from 351 failed / 1950 passed at HEAD, and the
calculations and aggregation lanes together from 596 failed / 1124 passed at
HEAD to 549 failed / 1173 passed. Of the residual registry-domain failures only
18 are absent from the HEAD baseline, and every one of those traces to an
external cause recorded below rather than to this migration.

Two dev-registry modules carried no lane marker and aborted the whole lane
before any test ran; both were given the lane's standard marker pair.

Three external conditions bound the result and are not owned here. The
identifier rename landed in the registry TOML corpus but the bundled authority
artifact was not republished, so it still registers the superseded ids; the
renamed tests are correct against the corpus and fail against the artifact until
a republish runs. A concurrent change replaced the `TaxDomain` enum with a plain
`str` subclass carrying a custom constructor, which pydantic cannot build a
schema for; every model annotating that type now fails at import, so the whole
registry domain, and with it all five lanes, stops at collection. Separately,
`m303_carry_header_key` is absent from its module, which fails the application
modelo `conftest` at HEAD as well as here.
