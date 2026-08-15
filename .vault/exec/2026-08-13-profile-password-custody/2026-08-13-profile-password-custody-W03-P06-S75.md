---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e0fd37c208764b94894d63ce9414d5b058a3f3a10595fef02ff230125d459302'
step_id: 'S75'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh clear the six dead entries in the runtime bootstrap-exempt allowlist that name operator verbs the tree no longer registers, since each entry grants exemption from the active-profile session gate matched by command chain, so a future verb registered under one of those names silently inherits an exemption nobody consciously granted, which matters most for the profile deletion verb, and note one further non-resolving entry is a deliberate exemption for a separate module entrypoint rather than a defect

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Description

- Absorb this step into the subtree ruling, since both act on the same verbs.
- Remove the dead exemptions in the same change as the declarations they guard.
- Measure the result with the command builder's own resolver.

## Outcome

Executed inside the operator-subtree step rather than separately, because the
entries name the same verbs whose declarations that step removed. Splitting them
would have left exemptions granting a bypass for verbs whose declarations were
already gone -- exemptions failing open, which is the defect this row exists to
close, reintroduced by sequencing.

The allowlist now carries twenty-four entries with none unresolving, measured
through the command builder's own resolver rather than a directory walk. That
distinction was load-bearing: a first attempt using a naive walk reported all
thirty entries dead, because it did not materialise lazy subtrees. Acting on
that number would have deleted every exemption in the file.

## Notes

Two findings from this file are recorded elsewhere because they outlive the row.

One removed entry justified itself by citing a test that does not exist, and
carried a real security principle nothing else records: a verb whose output
leaves the encrypted store must stay login-gated, because a target-scoped unlock
does not establish recency. That principle is rowed for the archive export work
to inherit.

A second entry explains its exemption by asserting the command reads plaintext
manifests, which it no longer does. The exemption stays correct on other grounds
but its stated reason is false.

**Two false justifications in one file in one day is the finding.** The
exemptions were right and their reasons were wrong, which is more dangerous than
an uncommented allowlist: a reader who checks the reasoning is misled, and a
reader who trusts it inherits a claim nobody has verified since it stopped being
true. An allowlist is exactly where the campaign's rules place the judgement, so
its reasons carry the same weight as its entries.

This record is written after the step was marked complete, which the plan gate
reported. The work was done and correct; recording it late is the same
discipline gap the campaign has now met three times today, in all three of its
directions -- a step checked without a record, a ruling delivered without one,
and here a row absorbed into another without one.
