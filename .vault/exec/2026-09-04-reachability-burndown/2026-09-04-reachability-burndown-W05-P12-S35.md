---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:17b1b5bb407d9d450f16e2a864c4067c5840385cb18e0b2ce4479b31c4254c35'
step_id: 'S35'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Record the paid-down unused-symbol debt the earlier deletion sweep left unwritten (six modules lowered, nine spent entries removed, no line added for the one peer finding the ratchet refuses to absorb), and adjudicate the eight findings referenced nowhere in the tree as should-be-live rather than deleting them: a custody record bound whose siblings are enforced and it is not, an unreachable flow-checkpoint discard, the unwired half of portable profile import beside its already-classified result type, two declared type distinctions nothing annotates, a sectoral retencion rate set no classifier consults, and the censo divergence projection that keeps unadopted certificate statements from the operator

## Scope

- `dev/quality/unused_symbol_ratchet.toml`

## Changes

- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/quality/tests dev/audit/tests/test_reachability_classification.py -m ""` -> `pass`

## Notes

The unused-symbol ratchet stays red on one added finding,
`non_filing_axis_parameters` in `_validate_parameter_temporal`, landed two
commits earlier by peer work grounding the non-filing axis. Its only reader is
its own test, and the governing ADR requires the admission be "enumerable and
gated in both directions", so it is capability in flight rather than residue. It
was deliberately NOT given an intentional disposition: 225 findings in this tree
have a test as their only reader, and admitting that as design-time authority
would empty the ratchet of meaning.
