---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f248b94e99b9161930730ffdff73a445ed586f3b9c3e9a99d039ecb9bbb7d51f'
step_id: 'S61'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate shipped agent harness action citations to canonical action identities

## Scope

- `src/cadrumo/_data/agent`

## Description

- Establish which envelope field the shipped operator-harness rules instruct the agent to read.
- Retarget every citation from the deleted suggestion field to the resolved action projection.
- State explicitly that an action resolving to a no-recovery outcome carries no automatic fix.

## Outcome

- The harness was handing the operator agent a dead instruction. Five citations across three shipped rules told it to read a suggestion field on the error envelope and on notices; this campaign deleted that field, and the live contract carries a resolved action in its place.
- That is the precise failure the CLI contract names: a harness citing a field the envelope no longer carries leaves the agent an instruction it cannot recover from, because nothing in the response will ever satisfy it.
- All five citations now name the action projection, and no field citation to the deleted surface remains in the shipped rules.
- The refusal-recovery guidance gained a sentence the previous wording could not express: an action that resolves to a no-recovery outcome is telling the agent the refusal has no automatic fix, so it must not invent one. Under the old field a missing suggestion was indistinguishable from an unstated one.
- The harness and rule-surface conformance selection passes eleven tests.

## Notes

- This is a shipped-data change rather than a code change: these rules travel with the package and are loaded into the operator agent's context, so a stale citation degrades every session that reads them.
- No carry-forward.
