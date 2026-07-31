---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:e9ed32ad8b2ee5a36dd46900d0755e3a4e15e9c397359d70226e5dd9d2eaac07'
step_id: 'S22'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Emit a bucket event for invoice linkage so the sole invoice-linkage writer leaves an audit trace like every neighbouring ledger mutation, co-committed in the same unit of work as the two catalogue writes, gated on a test asserting the event is appended atomically with the link and absent when the link is refused

## Scope

- `src/cadrumo/application/ledger/_actions_manual.py`
- `src/cadrumo/application/invoices/_linking.py`
- `src/cadrumo/domain/buckets/_event.py`

## Description

- Add a closed-set member for the linkage event alongside the other ledger transaction lifecycle tokens, after confirming no existing member covered the concept under any of three naming variants.
- Emit the event from the sole invoice-linkage writer, reusing the bucket-event builder the ledger package already owns rather than introducing a second emission authority.
- Give the linking service an opaque extra-writes slot so the event rides the same secure-object batch as the two catalogues, keeping exactly one persistence path and leaving the invoice layer free of event-history concepts.
- Carry identifiers and the operator's verb in the payload, never invoice content.
- Enroll the member in the ledger history filter so the event is visible to the verb an operator actually reaches for.
- Narrow the pre-existing evidence-isolation test to its stated intent, and add a real-adapter module covering emission, refusal, and rollback.

## Outcome

The one verb that binds a transaction to an invoice now leaves an audit trace, closing the last asymmetry between it and every neighbouring ledger mutation. Because the event write is composed into the same batch as the two catalogue writes, a crash can neither record a linkage that did not land nor land one silently; the three states are all-or-nothing together.

Three real-adapter tests: an empty-before and exactly-one-after emission check that also asserts no invoice content reached the payload, a refusal leaving the history untouched, and a mid-batch revision conflict rolling the event back alongside both catalogues. No mocks, stubs, or skips.

## Notes

A pre-existing test asserted that the whole event list was unchanged across a link. That held only while linkage emitted nothing, so it read as an invariant when it was really an artefact of the gap. Its stated intent — that linkage must not touch evidence — is preserved and now stated more precisely: the evidence history is identical either side and exactly one linkage event is added. Weakening it to assert nothing would have discarded a real guarantee.

Enrolling the member in the history filter was not in the original finding but is what makes the fix real. An event written to storage but excluded from the only verb that reads it would have been dormant capacity, satisfying the letter of the finding while leaving the operator exactly as blind.

The writer's file carried another campaign's uncommitted edits. Reading the full diff rather than grepping for expected markers is what caught them: a marker search for the peer's main symbol returned clean, while the actual diff held two unrelated peer lines. Those were reverted in a scratch copy before the HEAD-anchored own-only patch was built, and the working tree still carries them untouched. This time the working-tree edit came first and the staging second, so no unimportable window opened.
