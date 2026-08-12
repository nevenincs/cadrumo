---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:060f02fe7329cbf144e619082eab9aead406542d8f181033ba0bea27b35acb2e'
step_id: 'S109'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Close the split-declaration debt that reds tree-wide gates this campaign cannot declare complete over, taking each instance as a measured case rather than a sweep: the transaction field-role enum gained two members without its member-set fixture enumerating them, and the import-hygiene gate reports more test-only private reaches than its documented debt count admits. Establish for each whether the fixture or the count is the thing that is wrong before changing either, since a gate whose ceiling is raised to match reality detects nothing afterwards, and pin the property rather than the tally

## Scope

- `src/cadrumo/domain/transactions`
- `src/cadrumo/tests`

## Description

- Measure each half of the debt separately rather than treating the row as one
  sweep.
- Judge every import-hygiene instance as its own case: repoint, document, or
  delete.
- Bring the gate from five red assertions to nineteen green.

## Outcome

Delivered, and the two halves came out differently.

FIRST HALF, premise expired. The transaction enum member-set fixture is
complete and green: it pins the exact membership of the direction, lifecycle
and split-role enums and round-trips every member through its own value. The
exact-membership shape is right here rather than a tally to be distrusted --
these are closed sets, and the fixture own docstring gives the reason, that
adding a member should be a reviewable test diff rather than silent drift.

SECOND HALF, real and closed. Five gate assertions were red. Every instance
was judged on its own, because the row is right that a ceiling raised to match
reality detects nothing afterwards:

One PRODUCTION violation against a hard-zero baseline -- a registry module
reaching a core private module from inside a function for a symbol that is
already on the core facade, in a module that already imports that facade at
module level. No cycle to break, so the function-local private import simply
joins the facade import.

One reach REPOINTED rather than documented, which is the judgement the row
asks for: the symbol is exported by core, so naming its private defining
module was a citation error and not debt at all.

Seven test-only reaches documented with a reason each, after reading every
site. Five are genuinely white-box: the assertion IS about the private symbol,
and reading it through a double would assert the double. Two carry an honest
observation instead of a clean justification -- the sede error type is
arguably part of that boundary contract and wants promotion, and a
domain-layer test reaching application aggregation inverts the dependency
direction and wants either a promotion or a move.

Four stale entries deleted, on the gate own stated reasoning: an entry that no
longer answers a live reach is a spare slot that silently widens the gate.

## Notes

Three of the four stale entries were INVISIBLE until the earlier assertions
stopped failing, which is worth recording as a property of stacked gates
rather than as an incident: the staleness check runs after the set-equality
check, so a red set-equality assertion hides however much stale debt sits
behind it. The first pass found one; clearing the set brought three more into
view.

One entry added here is mine rather than inherited: the nested projection
parity gate widened an existing cross-package import from one payload model to
six, so its recorded name set was corrected in the same pass rather than left
to look like a new undocumented reach.
