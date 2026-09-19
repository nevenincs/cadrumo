---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:79cce3198d63f06598e869a3a30243da566950d31ebccaed428bf64f1f6e05bb'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `S115 related-party locator follow-up`

## Scope

Follow-up to deterministic S116 locator drift for the existing
`rows.related-party-operation` census row. Scope is limited to its capability
and grounding locators, the focused mutation gate, and S115 tracking.

## Findings

### S115 related-party locator | medium | adjacent dispatch line was stale

The live `per_related_party_operation` dispatch is the RELATED_PARTY branch at
`_row_set_assembly.py:170`. Both the census capability locator and the
repository grounding locator named adjacent line 168. The correction moves both
references mechanically to 170; it does not change the existing
`ingress_blocked` disposition, owner, review condition, expiry, or follow-up.

### S115 related-party locator | low | mutation gate awaits the shared end-to-end lane

The focused test checks the live locator against discovered capability evidence
and mutates it back to 168. The canonical locator gate rejects that mutation as
capability-locator drift. The direct runtime invocation did not yield a
terminal result within the shared-worktree execution window, so it is not
claimed as passed here; S116's canonical comparison is the requested
post-commit end-to-end proof.

## Recommendations

Retain the exact-dispatch mutation gate. Independent review should verify the
scoped correction after the focused locator lane reaches a terminal result.
