---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6e24c01c563c561c59ad40af5da52f43559e01d9b6594df3e41c251968898d98'
step_id: 'S103'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Split the handoff-audit cluster on evidence its class was hiding: the relation-consumption predicate it carried is a one-line convenience over a sibling with six production references, since the live callers each need the channels rather than a boolean, so delete it with its export and point its two registry tests at the function it wrapped. The two audits beside it stay open, and the same sibling comparison sharpens them, because relation consumption IS computed live and what is missing is the audit over it rather than the ability to compute it.

## Scope

- `src/cadrumo/domain/calculations/registry/handoffs.py`
- `src/cadrumo/domain/calculations/registry/tests/test_cross_period_relation_consumption.py`
- `src/cadrumo/domain/calculations/registry/tests/test_cross_dependency_contract.py`
- `dev/quality/unused_symbol_ratchet.toml`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/handoffs.py`
- `M` two registry test modules repointed at `relation_consumption_channels`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1031 -> 1030,
  exact 401 -> 400; the predicate is no longer reported
- `verify:` `pytest` on both repointed modules 1 failed / 18 passed, IDENTICAL
  against `git show HEAD:` of all three changed files, so pre-existing
- `verify:` symbol-ratchet entry lowered 3 -> 2 in this step; no shrink or spent
  lines remain
- `verify:` the four ledger gates 27 passed; module ratchet, secure-store gate
  and docstring ratchet exit 0
- `verify:` `ruff check` and `ty check` clean

## Notes

The finding here is about the ledger's own shape as much as the code. This
cluster was classed `should-be-live` and carried three symbols, and one of them
was not that class at all: `relation_is_consumed` returned
`bool(relation_consumption_channels(relation, index))` and nothing more. Its
sibling carries six production references -- `relation_prefill`, `work_review`
and `source_connectivity` each need the CHANNELS rather than a boolean, which is
exactly why the predicate collected only tests.

So a cluster's class can hide a member that belongs elsewhere, and the sibling
comparison is what surfaced it. The predicate is deleted with its `__all__`
entry and the two registry tests now call the function it wrapped; the cluster
keeps the two audits it was actually about.

That comparison sharpens what remains, too. Relation consumption IS computed
live, so the audits are not a missing capability to compute anything -- they are
a missing audit OVER a live computation, which is a different and smaller ask
than the entry implied.

One failure in the repointed modules reproduces identically against
`git show HEAD:` of all three changed files.
