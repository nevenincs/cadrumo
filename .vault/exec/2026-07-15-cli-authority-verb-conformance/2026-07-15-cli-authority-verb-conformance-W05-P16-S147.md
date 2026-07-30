---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S147'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Update remaining operator-surface contract notes to the accepted grammar and authority semantics

## Scope

- `src/cadrumo/application/operator_surface/_contract.py`

## Description

- Read the operator-surface contract notes and confirm the child verbs and operator questions match the accepted grammar and authority semantics.

## Outcome

The contract notes carry the accepted grammar. The config surface declares logout, passphrase, recovery, and reset children, and each operator question describes the accepted semantics accurately: the recovery child is described as inspecting, enrolling, rotating, and verifying the custody recovery code without exposing it, and the reset child as starting, inspecting, or resuming the durable all-profile configuration reset.

The recovery question is notable because it states the confidentiality posture in the contract itself, which agrees with the secret-free schema shapes verified in the preceding Phase.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
