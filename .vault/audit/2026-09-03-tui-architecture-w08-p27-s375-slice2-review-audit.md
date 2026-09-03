---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:b0e544b054460dbcad6f5312b75680e0896a9207b3bb7f30ce8a09c996c10273'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---
# `tui-architecture` audit: `W08.P27.S375 slice 2 independent review`

## Scope

Independent review of the live classification and prepared-import slice, including controller, routes, presentation models, screens, tests, and all shipped locale copy. The review traced catalogue authority, classification patch meaning, explicit mutation confirmation, import command secrecy, admission and refusal, asynchronous state transitions, error copy, semantic focus, eighty-column geometry, one-scroll behavior, forbidden imports and I/O, and whether tests exercise production invariants rather than matching local fixtures.

## Findings

### invisible-classification-target | high | Closed: classification target is visible and admitted from the projection

The initial screen hid its target and accepted an off-projection identity. Remediation rejects a classification target absent from the injected entry catalogue and renders its projection position, total, and safe twelve-character reference before confirmation. Exact admission and rendered-coordinate tests close this finding.

### prepared-import-is-not-opaque-or-stable | medium | Closed: prepared import is immutable, vaulted, non-serializable, and safely identified

The initial object exposed and permitted replacement of its command, serialized protected path and provider values, and admitted unsafe or duplicate display identities. Remediation moves the command into a module-private weak vault, makes instance metadata immutable, refuses pickle serialization, constrains label keys and choice grammar, and rejects duplicate ids before mounting. Exact adversarial tests close this finding.

### terminal-flow-state-can-be-rewritten-as-cancelled | medium | Closed: terminal and in-flight lifecycle states are guarded explicitly

Remediation makes flow transitions monotonic, accepts Confirm only from `CONFIRMING`, disables both controls during submission, and prevents post-success Cancel or repeated submission. Submission now runs in an owned worker so keyboard messages remain responsive, and `action_back` explicitly refuses Escape while `SUBMITTING` without posting a back request or unmounting the screen. Slow-door compositor tests prove that behavior for both classification and import through successful settlement. A failing import door carrying a protected path and provider also proves that only localized generic failure copy is rendered. This finding is closed.

### new-screen-geometry-tests-are-proxy-only | low | Closed: both new screens have exact compositor and focus assertions

The new parameterized compositor test now asserts initial and confirming focus chains, `geometry_band`, zero horizontal table scroll, and the sole permitted vertical scroll owner for both Classification and Import at eighty columns. This proof gap is closed.

## Recommendations

No open recommendation remains from this review. The high target-confirmation finding, both medium findings, and the low geometry proof gap are closed. Slice 2 is safe to proceed.

Positive findings: classification action identity is validated through the real application catalogue and its canonical command key; the classification patch changes only `business_classification`; mutation requires a separate row selection and confirm action; absent submitters and still-deferred destinations resolve to typed refusals; import paths and providers do not appear in current screen copy, custom repr, or generic failure messages; flow modules import no adapters, CLI, file readers, or concrete import mutator; locale strings are authored and genuinely distinct in all four languages; Escape cancels pre-submit confirmation before returning to the parent; and direct eighty-column compositor inspection found no clipping or horizontal scrolling.

Focused gates: 24 Ledger tests passed with all markers enabled; Ruff passed; ty passed; basedpyright reported zero errors and zero warnings. These gates do not discharge the findings because the current tests omit the reproduced adversarial states.

