---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:75928b888403d482f79df7bc706f1ac03b0883689841496aeb9a90aca237238b'
step_id: 'S101'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the three public result projectors the CLI payload contract displaced, since each is a one-line construction of a matching model, none is called in production, dev or tests, and the command table declares the verify leaf schema as a deferred target on the CLI payloads module so the richer payload is what ships. Check first that the models survive the deletion, which they do because each is bound as a result type on a live operation definition, and lower the symbol-ratchet entry in the same step rather than the next sweep.

## Scope

- `src/cadrumo/application/modelo/operation_definitions.py`
- `dev/quality/unused_symbol_ratchet.toml`
- `dev/audit/tests/test_ledger_citations_resolve.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/audit/tests/test_ledger_citations_resolve.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1033 -> 1031,
  exact 404 -> 401; none of the three still reported
- `verify:` `pytest .../modelo/tests/ -k operation` 4 failed / 81 passed,
  IDENTICAL against `git show HEAD:` of the changed file, so pre-existing
- `verify:` symbol ratchet entry lowered 5 -> 2; only the two peer regressions
  remain
- `verify:` the four ledger gates 27 passed; module ratchet, secure-store gate
  and docstring ratchet exit 0
- `verify:` `ruff check` and `ty check` clean; module imports, 50 exports

## Notes

The order of checks mattered more than the deletion. The evidence said the three
PublicResultV1 models had left this cluster because their projectors construct
them, and a construction counts as a use -- which would mean deleting the
projectors newly orphans three models and trades one finding for another. It
does not: each model is also bound as `result_type` on a live
`OperationDefinition`, so it stays reached on its own. Checking that BEFORE
deleting is what made this a clean three rather than a swap.

The displacement itself was already named rather than guessed: the command table
declares the verify leaf result schema as a `DeferredTarget` on
`entrypoints/cli/_modelo_payloads`, and the two shapes diverge deliberately --
the payload carries resolved and missing casilla ids, findings, run_at and
verified_by where the PublicResultV1 carries counts. The richer contract is the
one that ships.

The symbol-ratchet entry went five to two in this step. Twice before this
campaign has owed that bookkeeping to a later sweep; doing it here cost nothing.

The citation gate then refused the entry, correctly and for a shape I had only
half-anticipated. Resolution BY DELETION leaves a citation no live file can
satisfy -- the same impossibility as the empty-symbols case, arriving by a
different route. The subject rule now steps aside for a `resolved` entry, as the
staleness check already does, while existence is still required of every
citation; two teeth cases pin both halves.

Four tests in the modelo operation suite fail identically with and without this
change. Peer work in flight on the operation-definitions surface, consistent
with the receipt failures seen in the previous step.
