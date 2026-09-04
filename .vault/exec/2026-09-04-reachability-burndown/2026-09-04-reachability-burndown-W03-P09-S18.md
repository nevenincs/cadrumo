---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:c05150fa2461548e7103a3ca8f1ad5cc23613fe08f32eae11920ece2772d0e98'
step_id: 'S18'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Adjudicate the 76 names defined with DIFFERENT values across modules, where merging would be wrong and one side needs renaming

## Scope

- `dev/audit`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/errors.py`
- `M` nine application modules composing the canonical set
- `A` `src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py`
- `verify:` `uv run --no-sync lint-imports` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py` -> `pass`

## Notes

Adjudicating the different-value collisions found that most are not hazards at all. The
largest are per-module idiom whose value differs only because the module does: `_log`,
`_logger`, `_LOGGER` and `_LOG` are all `get_logger(__name__)` across 161 sites, `ENTRY` is
one portal record per portal module, and `_METADATA`, `_READ`, `READ_GUARD_POLICY` and
`_COLUMN_KEYS` are per-command or per-view declarations that are supposed to differ. The
sweep counts them because it compares rendered values, not because they collide.

Two were real, and one was a latent defect.

`STORAGE_DEGRADATION_ERRORS` was declared nine times. Seven modules carried the same three
errors; `prorrata_regularizacion` added `ProrrataRegisterError` and
`_modelo_bindings_support` added four persistence errors. The extensions are legitimate,
but the base set was restated nine times, so adding a fourth error the engine should
degrade on means editing nine places -- and the copy nobody edits keeps RAISING where its
siblings report an incomplete source. That failure runs in the direction
`no-silent-under-declaration` forbids: a caller that does not degrade produces a total
rather than an advisory.

The set now lives once in the module that defines the error classes, consumers import it,
and the two extenders compose it. All three tuples were verified to reproduce their exact
previous members. Because this adds a persistence-layer import to application modules, the
architecture was checked rather than assumed: 11 contracts kept, 0 broken.

`_WHITESPACE_RE` is the second, recorded here and not yet resolved: `adapters/inbound/pdf`
compiles `\s` while three other modules compile `\s+`. Those are different matchers --
one whitespace character against a run -- so a substitution written for one collapses runs
and the other does not. It needs its own Step rather than a blind merge.

## Notes on the gate

The gate forbids RESTATING the base members while allowing composition, so the two genuine
extenders stay legal. Teeth proven by restating the tuple in `multi_year`: the gate exits 1
naming the module, and exits 0 once restored.

Five failures in the aggregation and invoices suites are pre-existing, proven by A/B
against copies of all nine unmodified modules: 5 failed and 1176 passed identically with
and without the migration.
