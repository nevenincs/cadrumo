---
tags:
  - '#audit'
  - '#facturae-invoice-class'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:67b235fffc9a561912e6c210b5239e59effd2640f3110db6452faa1d269b0a35'
related:
  - '[[2026-08-13-facturae-invoice-class-plan]]'
---



# `facturae-invoice-class` audit: `implementation closeout`

## Scope

- Reviewed the accepted decision and completed L1 plan against the five implementation commits.
- Examined the typed parser boundary, draft resolution order, closed finding axes, confirmation mappings, and real-storage corpus tests.
- Checked for silent class collapse, parser over-refusal, dishonest discrepancy reuse, public draft-contract drift, and test shortcuts.

## Findings

No critical, high, medium, or low findings remain open.

### invoice-class-branch-coverage | medium | The closed vocabulary's downstream semantics are not gated exhaustively

The feature tests exercise the real-corpus `OO` and `OR` paths, the absent-code fallback, and only the ordinary-code-with-corrective-reference contradiction. They do not exercise the `CO` and `CR` copy mappings, either `OC` or `CC` recapitulativa blocker, or the reverse contradiction where a declared corrective code carries no corrective reference. The vocabulary equality test proves membership only, so all four unexercised codes could be routed to the wrong downstream class or finding while the committed feature suite remained green. This leaves the completed `S03` six-code partition and `S04` discrepancy totality supported by inspection rather than a non-tautological executable gate.

Resolved in `d9c6a809b4`. The real evidence-storage suite now drives `CO` to ordinaria, `CR` to rectificativa, both `OC` and `CC` to the unmodelled-class finding while retaining an operator-supplied simplificada class, and both `OR` and `CR` without a corrective reference to the contradicted-class finding. The complete feature-focused gate passes forty-eight tests.

## Recommendations

- Keep the deferred domain-level recapitulativa taxonomy change separate, as required by the accepted decision.
- Treat the forty-two-test result as feature-scoped evidence only; repository-wide gates remain independently authoritative.
- Add table-driven parser-to-draft coverage for all six corpus-grounded enum members, asserting `CO` as ordinaria, `CR` as rectificativa, `OC` and `CC` as unmodelled, and both declared-class/corrective-reference contradiction directions. Keep the existing real-corpus `OO` and `OR` confirmation journeys as the end-to-end anchors.
