---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:98da0bd13f00846908628eca7d1162586bcabc614c7d31083e7a0058410a806d'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---
# `tui-architecture` audit: `W08.P27.S375 slice 2 independent review`

## Scope

Independent review of the live classification and prepared-import slice, including controller, routes, presentation models, screens, tests, and all shipped locale copy. The review traced catalogue authority, classification patch meaning, explicit mutation confirmation, import command secrecy, admission and refusal, asynchronous state transitions, error copy, semantic focus, eighty-column geometry, one-scroll behavior, forbidden imports and I/O, and whether tests exercise production invariants rather than matching local fixtures.

## Findings

### invisible-classification-target | high | The operator confirms a mutation without seeing or validating its transaction target

`LedgerClassificationScreen` renders only a generic selected-entry prompt and classification choices. It never renders even the safe transaction prefix used by Entries and Review, while the factory accepts any syntactically valid `TransactionId` as `classification_target` without proving that it belongs to the injected projection. Confirmation therefore gives the operator no way to verify which entry will be mutated, and the controller will submit an off-projection target unchanged. The existing test verifies the hidden target only after submission, which proves plumbing rather than informed confirmation. Admission must reject a target absent from the projected entry catalogue, and the confirmation surface must display a safe semantic target coordinate.

### prepared-import-is-not-opaque-or-stable | medium | The prepared command can be read, replaced, and serialized after admission

`LedgerPreparedImportV1` claims an opaque pre-resolved command with no serialization surface, but `_command` is directly accessible and assignable. Its default pickle representation contains the protected filename and provider, and replacing `_command` after display causes the same identity-approved object to submit a different path and provider because controller membership is object identity. `choice_id` is only checked for non-emptiness, is emitted by `repr`, and can itself contain sensitive text; duplicate ids can also collide in `DataTable`. The focused test checks only the custom `repr` and rendered Static copy. Make the prepared capability immutable, constrain safe identities, reject duplicates, and either prevent serialization or define an explicitly redacted serialization contract.

### terminal-flow-state-can-be-rewritten-as-cancelled | medium | Cancel remains live after a successful persisted operation

Both flows leave their controls and selection live after terminal success or failure. In a real compositor probe, selecting Cancel after a successful import changed `flow_state` from `SUCCEEDED` to `CANCELLED` while the import door retained its completed call. This is a false lifecycle claim: cancellation cannot undo the persisted mutation. Submission controls should be disabled or guarded outside the confirming state, terminal results must remain terminal, and in-flight cancellation/back behavior must have an explicit policy. Tests cover only one happy submit and pre-submit cancellation, not post-success cancel, repeated confirm, slow in-flight submission, screen teardown, or cancellation exceptions.

### new-screen-geometry-tests-are-proxy-only | low | Flow tests use 80 columns without asserting geometry, scroll ownership, or focus order

The slice tests mount both new screens at 80 columns but do not call the established geometry probe, inspect horizontal scroll, assert one vertical scroll owner, or assert the focus chain. Independent compositor inspection currently found no overflow, zero horizontal table scroll, and sensible semantic focus order for both screens, so this is a proof gap rather than a reproduced layout defect. Enroll Classification and Import in the same non-vacuous geometry, scroll, and focus assertions used by the existing Ledger surfaces.

## Recommendations

Hold further S375 slices until the high target-confirmation defect and the two medium secrecy/lifecycle defects are corrected with independent tests. The low proof gap should close in the same follow-up because the shared geometry primitives already exist.

Positive findings: classification action identity is validated through the real application catalogue and its canonical command key; the classification patch changes only `business_classification`; mutation requires a separate row selection and confirm action; absent submitters and still-deferred destinations resolve to typed refusals; import paths and providers do not appear in current screen copy, custom repr, or generic failure messages; flow modules import no adapters, CLI, file readers, or concrete import mutator; locale strings are authored and genuinely distinct in all four languages; Escape cancels pre-submit confirmation before returning to the parent; and direct eighty-column compositor inspection found no clipping or horizontal scrolling.

Focused gates: 24 Ledger tests passed with all markers enabled; Ruff passed; ty passed; basedpyright reported zero errors and zero warnings. These gates do not discharge the findings because the current tests omit the reproduced adversarial states.

