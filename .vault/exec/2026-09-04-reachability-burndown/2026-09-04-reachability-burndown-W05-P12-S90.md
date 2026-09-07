---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:ba566efc73cb3e08610d0e41673f864f3709272395bf6899876faf364d099139'
step_id: 'S90'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Sweep every open cluster for the stale-prose shape found twice by reading, then correct the one false docstring the sweep's subject exposed: five clusters name a live symbol inside an unreached-claim sentence and all five are legitimate contrast mentions, so no further staleness exists. The filing-status token's docstring asserted that mounted live command families use it while none reads it, and a sentence claiming a wiring the tree does not have outranks the code until someone checks; correct it rather than leaving the false half waiting on the routing decision.

## Scope

- `src/cadrumo/application/operator_surface/models.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/operator_surface/models.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest dev/locales/tests/test_contract.py` 26 passed -- the one true
  consumer of the token
- `verify:` the three ledger gates 19 passed; `docstring_reference_ratchet`
  exit 0; module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1038, exact 409
- `verify:` `ruff check` and `ty check` clean

## Notes

The sweep was a negative result and its limitation is the more useful half. It
looked for open clusters whose unreached-claim sentence names a symbol the audit
reports as live, and found five, all legitimate: each names the DISPLACING or
contrasting construct, which is what such a sentence is made of. An earlier
attempt matched prose against the ledger's own symbol lists and returned zero by
construction -- the defect is a sibling REMOVED from a list, which leaves no
trace in the ledger to match against. Both real instances were found by reading,
and prose drift stays authorial.

What the sweep did surface is that its subject carried a false docstring. The
filing-status token said it IS the canonical live-read token used by mounted
live command families. None reads it; outside its module the only true reference
is the locale-contract test. A docstring asserting a wiring the tree does not
have is a claim a reader has no way to check, and it outranked the code for as
long as it stood.

Corrected rather than deferred. Whether to route the live families through the
token or withdraw it is an owner's call and stays open, but the false half did
not have to wait on it. Reclassified staged rather than orphaned: the vocabulary
the token declares is the one a live family would report against, and its single
member names the only status such a family could report today.
