---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:486f7de42d1763fa42d46ea83c89ab447ddf0f41ffbc66e7bb32b29883ed617c'
related:
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
  - '[[2026-08-11-tui-architecture-plan]]'
---
# `tui-architecture` audit: `W08.P27.S375 slice 3 independent review`

## Scope

Independent review of the live evidence and reconciliation slice, including controller, routes, presentation models, screens, tests, and all shipped locale copy. The review traced evidence metadata sensitivity, catalogue authority, mutation admission, reconciliation source truth, affected-declaration meaning, asynchronous state transitions, Escape and repeated-submit behavior, refusal and stale-authority handling, semantic identity and focus, eighty-column geometry, one-scroll ownership, forbidden dependencies, and whether tests prove production invariants.

## Findings

### reconciliation-selection-is-positional | high | Closed: selection now resolves the exact semantic row identity

The initial handler indexed the immutable projection with `cursor_row`, so reordered presentation could submit another visible pair. Remediation reads `event.row_key`, resolves that semantic transaction/invoice identity against the injected projection, and rejects a key absent from the visible authority. A two-suggestion compositor test sorts the table into an order different from the projection, selects its first visible row, and proves that the exact selected pair reaches the injected link door once. This finding is closed.

### reconciliation-source-facts-are-reclassified-or-dropped | medium | Closed: presentation now formats application-owned score, match facts, and direction

The initial screen invented a frontend Full/Partial category, ignored the canonical score, and omitted inconsistency direction. Remediation removes that classification and renders the injected canonical score plus separate amount-match and counterparty-match facts with localized Yes/No values. It maps the canonical inconsistency direction to explicit localized operator copy and refuses unsupported direction values instead of guessing. Multi-field rendered-copy assertions now pin the application-owned meaning. This finding is closed.

### reconciliation-copy-tests-are-partially-vacuous | low | Closed: all locales and semantic distinctions have exact assertions

The initial tests checked only that `AEAT` appeared and that evidence titles differed. Remediation adds exact expected local-only/AEAT-separation text, canonical score, both match labels, and inconsistency direction for English, Spanish, Catalan, and Hungarian. The separate reordered two-row test also closes the fixture weakness. This finding is closed.

## Recommendations

No open recommendation remains from this review. The high mutation-identity finding, medium source-truth finding, and low proof gap are closed. Slice 3 is safe for final review.

Positive findings: evidence rendering limits itself to safe manifest presentation facts and does not expose provider locators, hashes, linked invoice identities, or full attachment identities; both evidence and link capabilities are validated against the real injected application catalogue; link submission admits only a visible injected transaction/invoice pair and validates returned identity; affected declarations visibly separate Modelo, period, and changed/removed counts; the page explicitly states that it shows local Ledger evidence and that AEAT Sync is separate; absent dependencies, unavailable applications, and still-deferred routes produce typed refusal; workers disable controls, reject in-flight Escape and repeated submission, preserve generic localized errors, and restore semantic focus; all four locales contain real authored strings; eighty-column compositor checks show no horizontal table scroll and one page scroll owner; and the slice imports no adapters, CLI, file readers, action implementations, or concrete services.

Initial focused gates: 40 Ledger tests passed with all markers enabled; Ruff passed; ty passed; basedpyright reported zero errors and zero warnings. Final remediation probe: all 15 slice-3 tests passed with all markers enabled, including the semantic reorder and all-locale assertions; focused Ruff passed.
