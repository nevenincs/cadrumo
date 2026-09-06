---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:659e265ff4e9191503c09afcfe9dee17c0c7ba97b2ae2e189db6d7e3e0be8523'
step_id: 'S28'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Obtain the owner decisions the three blocked modules need, since classification is evidenced and none can be recorded without them: re-wire or withdraw the ledger import-preparation capability its contract still requires, and either record the decision the two staged domain packages are waiting on or withdraw them

## Scope

- `src/cadrumo/application/ledger/import_preparation.py`

## Changes

- `D` `src/cadrumo/application/ledger/import_preparation.py`
- `D` `src/cadrumo/application/ledger/tests/test_import_preparation.py`
- `D` `docs/api/cadrumo.application.ledger.import_preparation.rst`
- `M` `docs/api/cadrumo.application.ledger.rst`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.quality.unreachable_module_ratchet` exit 0 -- the
  campaign's standing red is gone, by withdrawal rather than by a baseline
- `verify:` ledger validated by direct script -- closed class vocabulary,
  evidence present, no symbol in two clusters, all seventeen cited paths resolve

## Notes

The step asked to re-wire or withdraw the capability. Withdrawn, because the
capability was never absent: the guard the module performs runs unconditionally
inside the action every caller already reaches, `_require_readable_source` at
`actions_import.py:483`, invoked first thing in `import_ledger_source` and again
from `_validate_import_source`. Both carry the same `--provider auto` rationale
in nearly the same words, which is what the deleted module's docstring meant by
mirroring the action's guard.

That also retires the remedy the old ledger entry named. It blamed the missing
TUI workspace route host, but a prepared import is submitted to
`import_ledger_source` like every other command, so the route host landing would
not have given the preparer a job.

The two staged domain packages this step also named need no further decision:
`domain.contabilidad` and `domain.is_compensation` each carry a
`declared_by_contract` intentional entry naming the production error codes
registered against their error classes, which is the recorded decision the step
asked for.

Regenerating the Sphinx stubs also scaffolded twelve stubs for modules a peer
added, since the tree had drifted. Those files are correct output for the live
tree and were left in place rather than reverted to a stale state.
