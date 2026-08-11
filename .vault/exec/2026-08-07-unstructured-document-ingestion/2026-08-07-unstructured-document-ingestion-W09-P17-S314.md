---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c8e3c4016f0b133f688b49a6dd3d15703cce427407ccd7d9963b7f534a7df95d'
step_id: 'S314'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Re-point the two consent-gate cross-references in the evidence draft text module at the module that actually defines the gate, since the cited adapter module does not exist

## Scope

- `src/cadrumo/llm`

## Description

- Read both consent-gate cross-references in the text reading module at HEAD.
- Confirm the cited target exists and is the module that defines the gate.

## Outcome

PREMISE EXPIRED. Both cross-references are already correct at HEAD, and the
row's stated reason for the change - that the cited adapter module does not
exist - no longer describes what they cite.

The module-level paragraph and the router entry point's docstring each name
the gate as the client's per-invocation evidence-consent check, both written
as a bare anchor on the client class. That class is the home of the check: it
is applied at the client's own dispatch choke point, which is the property
both paragraphs are asserting and the reason neither can be reached around by
constructing a request directly. Neither cites an adapter module, so there is
nothing to re-point.

No change made. Closed on the measurement rather than on a report.

## Notes

The bare-anchor spelling is the house style for project targets, and it is
also why this row could not be settled by the cross-reference gate landed
under S317: that gate deliberately judges only DOTTED first-party targets,
because a bare anchor carries no module claim to check. So the correctness
here rests on a reading, and a future regression of these two references back
to a dotted stale module WOULD be caught, while a regression to a different
bare anchor would not.
