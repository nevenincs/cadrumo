---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:c8d95d0084290bc7d7b7c2ffe669274307e03393f103cdddd506f50741727b6c'
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

### terminal-flow-state-can-be-rewritten-as-cancelled | medium | Open: terminal states are fixed but Escape can orphan an in-flight submission

Remediation makes flow transitions monotonic, accepts Confirm only from `CONFIRMING`, disables both controls during submission, and prevents post-success Cancel or repeated submission. The reproduced terminal-state rewrite is closed. A narrowed lifecycle defect remains: `action_back` handles only `CONFIRMING`; in `SUBMITTING` it delegates to the base action and posts `LedgerBackRequested` while the screen itself owns and awaits the submit coroutine. The host may therefore navigate away or unmount the only result owner during an in-flight mutation. No slow-door Escape, teardown, or generic failure test covers that state. This finding remains medium until in-flight Escape has an explicit refusal or lifecycle owner and an exact test.

### new-screen-geometry-tests-are-proxy-only | low | Closed: both new screens have exact compositor and focus assertions

The new parameterized compositor test now asserts initial and confirming focus chains, `geometry_band`, zero horizontal table scroll, and the sole permitted vertical scroll owner for both Classification and Import at eighty columns. This proof gap is closed.

## Recommendations

Hold further S375 slices until the remaining narrowed medium in-flight lifecycle defect is corrected and independently tested. The high target-confirmation finding, prepared-import secrecy finding, terminal-state rewrite, and low geometry proof gap are otherwise closed.

Positive findings: classification action identity is validated through the real application catalogue and its canonical command key; the classification patch changes only `business_classification`; mutation requires a separate row selection and confirm action; absent submitters and still-deferred destinations resolve to typed refusals; import paths and providers do not appear in current screen copy, custom repr, or generic failure messages; flow modules import no adapters, CLI, file readers, or concrete import mutator; locale strings are authored and genuinely distinct in all four languages; Escape cancels pre-submit confirmation before returning to the parent; and direct eighty-column compositor inspection found no clipping or horizontal scrolling.

Focused gates: 24 Ledger tests passed with all markers enabled; Ruff passed; ty passed; basedpyright reported zero errors and zero warnings. These gates do not discharge the findings because the current tests omit the reproduced adversarial states.

