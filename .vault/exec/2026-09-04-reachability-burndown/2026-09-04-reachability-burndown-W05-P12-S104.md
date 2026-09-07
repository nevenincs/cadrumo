---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4f5af587e31cbd6e49a5c3bed1b357ce389b17012f2df2f899e73e7bd7ae108e'
step_id: 'S104'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Sweep for the shape the relation predicate turned out to be, an unreached one-line delegator whose target is reached elsewhere, and delete the one real hazard it finds: the prorrata seed variant returned only the seed and dropped the operator-facing blocker and advisory findings its own docstring said to use the other function for, nothing called it anywhere, and the evaluator it wrapped is invoked by the register CLI. Repoint the two production docstrings that pointed readers at the discarding variant.

## Scope

- `src/cadrumo/application/prorrata_register/seed.py`
- `src/cadrumo/application/prorrata_register/sector_lifecycle.py`
- `src/cadrumo/core/prorrata_register.py`
- `dev/quality/unused_symbol_ratchet.toml`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/prorrata_register/seed.py`
- `M` `src/cadrumo/application/prorrata_register/sector_lifecycle.py`
- `M` `src/cadrumo/core/prorrata_register.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1030 -> 1029,
  exact 400 -> 399; the variant is no longer reported
- `verify:` `pytest .../prorrata_register/tests/` 31 passed
- `verify:` symbol-ratchet entry removed as spent in this step; no shrink or
  spent lines remain
- `verify:` the four ledger gates 27 passed; module ratchet, secure-store gate
  and docstring ratchet exit 0
- `verify:` `ruff check` and `ty check` clean

## Notes

The sweep generalises the previous step: an unreached function whose entire body
delegates to a name that IS reached elsewhere. Twenty-one hits, and twelve
delegate to builtins -- `tuple`, `dict.get`, `frozenset`, `re.fullmatch` -- which
is noise, since wrapping a builtin is not displacement. The rule to keep is that
the delegation target must be project-owned.

Two of the remaining nine were false on reading, and both taught the same thing:
a single call in the body is not the same as a pure delegation.
`render_fixed_width_export_record_payload` appends the record's line terminator
to what it delegates to, and `required_supply_nature_for_rule` distinguishes
"not grounded" from "grounded and silent" with its own `Raises` clause. Both add
behaviour the target does not have.

The real hazard is the prorrata seed variant, and it is the calculate-wrapper
shape again: it returned only the seed and dropped the operator-facing blocker
and advisory findings, its own docstring told the reader to call the other
function when those are needed, and nothing called it -- not production, not
dev, not tests -- while the evaluator it wrapped is invoked by the register CLI.
Deleted, with the two production docstrings that pointed at it repointed.

`registry_snapshot_id_for` was left alone: it is reached by a dev parity harness
and a registry test scenario, which is harness-code rather than dead.
