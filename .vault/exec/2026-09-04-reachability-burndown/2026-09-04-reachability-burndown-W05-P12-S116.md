---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4b121075a4dc0fb26e132adc7f16000478c420cdc3a763c533179e4cd6b5059a'
step_id: 'S116'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Close the gate-table consistency failure by enrolling the last unaggregated static check with its recipe's own command

## Scope

- `dev/quality/suite.py`

## Changes

- `M` `dev/quality/suite.py`
- `verify:` `uv run --no-sync python -m pytest dev/quality/tests/test_suite_gate_table.py -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.modelo_workspace_action_denominator` -> `pass`

## Notes

The gate table carries a second consistency check beyond membership: a row must
run the same command its recipe does. The first attempt at this enrolment
guessed a `-m dev.quality.modelo_workspace_action_denominator` invocation, and
that check refused it -- the recipe drives the gate through pytest against
`dev/tests/test_modelo_workspace_action_denominator.py`, because the denominator
is asserted by a test rather than by a module entry point. Two halves that can
disagree is exactly what the check exists to prevent, and it caught the
disagreement on the way in.

The recipe belongs to a concurrent migration and was enrolled rather than left
red because the gate already passes: the only thing its absence changed was
whether `just check-all` ran it, so the row alters no one else's check logic.

`dev/quality/tests/test_doc_privacy.py` still fails on three runner hostnames in
`.github/ci-control-plane.md`. That one is not resolved here: scrubbing the
names would empty a control-plane document whose purpose is naming which runner
is which, and allowlisting them is a decision about the operator's own machine
identities rather than a mechanical fix.
