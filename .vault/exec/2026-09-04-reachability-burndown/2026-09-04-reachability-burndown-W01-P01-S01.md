---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:458a0c42dac81815b2ba988a4a75453034c6442497b95c4e92d911fc701fa498'
step_id: 'S01'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Classify every unreachable and module-exec-only module by outside-use label and semantic uniqueness probe, recording the evidence behind each supersession or staging claim

## Scope

- `dev/audit`

## Changes

- `A` `dev/audit/reachability_classification.toml`
- `A` `dev/audit/tests/test_reachability_classification.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`

## Notes

All 17 in-scope module findings are classified; the other 26 are inside the deferred TUI
prefix and belong to its owning campaign.

The dominant finding is that most of this population is not dead code. Nine modules are
`staged-capability`, each backed by an ACCEPTED decision that records the dependency it
waits on -- the fincas titularidad record, the modelo edit contract, the compatibility
lifecycle. Four are `harness-code` whose only non-test consumers live in `dev/`: the
source-connectivity authority, the CRUD contract drift gate, and the registry export
pipeline. Two are `deferred-by-ownership` through the TUI supplier closure, one of which
the ratchet itself already reported as such. Exactly one, `application.wizard`
`_registered_values`, has no non-test consumer anywhere and is marked `orphaned` with its
remedy flagged as requiring an owner decision.

Grounding order mattered. Querying the decision corpus first was what separated staged
capability from orphans, and it inverted the naive reading: a name-based sweep would have
reported nine deletable modules that are in fact awaiting work someone already decided to
do. The semantic probe over production code is what surfaced the CRUD catalogue's real
consumer, whose own docstring then confirmed it.

The ledger is deliberately stricter than the duplication one in a way that matters: it may
NOT over-declare. A duplication entry outliving its clone is a landed consolidation, but a
classification entry outliving its finding leaves a reviewed-looking name that a future
regression could land on unnoticed, so a stale entry fails.

Five gates cover the ledger, all reading the live audit rather than a recorded count:
complete coverage, no stale entries, a closed class vocabulary, evidence present on every
entry, and a refusal to smuggle deferred modules into scope. Teeth proven for all six
defect shapes -- invented class, missing class, blank evidence, missing evidence, a
smuggled deferred module, and a dropped entry.
