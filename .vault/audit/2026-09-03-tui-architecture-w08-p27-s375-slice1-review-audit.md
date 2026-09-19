---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:a9cd29756c0ed6423cc19f6e55da18fff932844807ab1ac0099b52559b334930'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---
# `tui-architecture` audit: `W08.P27.S375 slice 1 independent review`

## Scope

Independent read-only review of the first `W08.P27.S375` Ledger workspace slice against the accepted navigation join and the live application-owned Ledger projection. Scope covered the exact route catalogue, injected projection and admission state, deferred destinations, overview hierarchy, entries and review source fidelity, redaction, action identity authority, semantic focus, Escape behavior, localization, eighty-column geometry, scroll ownership, forbidden authority acquisition, and whether focused tests prove those claims independently.

## Findings

### locale-fallback-masquerades-as-i18n | high | Closed: every shipped locale now has authored Ledger copy

The initial production labels called `ledger_copy` with `tui.ledger.*` keys and English defaults while none of those keys existed in a shipped locale catalogue. The remediation authors the Ledger subtree in English, Spanish, Catalan, and Hungarian; removes fallback defaults from production lookup; and asserts exact locale-specific overview, review, and status copy. The original high finding is closed.

### unmeasured-counts-render-as-zero | medium | Closed: navigation and overview preserve an unmeasured denominator

The initial navigation and overview tables rendered `item_count` unconditionally, presenting `Not measured` beside `0`. Navigation was corrected first; the overview initially retained the defect. Final remediation routes the overview quality table through `item_count_label` too, and an exact compositor test asserts its Evidence row is `Evidence`, `Not measured`, `Not measured` with no numeric zero. This finding is closed.

### review-filter-contradicts-projected-rows | medium | Closed: review copy now describes every projected status truthfully

The initial review screen claimed a pending-only filter while its valid application projection could include reviewed rows. The remediation changes the authored copy to all review statuses and adds an exact mixed Pending and Reviewed assertion. The presentation now follows the application-owned queue without frontend filtering, so this finding is closed.

### review-action-is-frontend-declared | medium | Closed: the factory validates and injects the canonical application action

The initial controller minted the review action locally and validated it against another local literal. The remediation requires an injected `ActionReference`, resolves it through the real application catalogue, refuses unknown and wrong-command actions, and propagates the injected reference unchanged to every review row. This finding is closed.

## Recommendations

No open recommendation remains from this review. All four findings are closed, with no open high or medium defect. Slice 1 is safe to proceed to slice 2; no route or architecture decision needs reopening.

The route catalogue covers the seven canonical areas exactly once; Overview, Entries, and Review are implemented while four deferred bodies resolve to typed truthful refusals; the outer factory retains the exact injected immutable projection and rejects the wrong destination context; entry payloads remain redacted; row and focus keys use semantic transaction identities; Escape posts a parent-return request rather than terminating the application; the eighty-column compositor reports no horizontal overflow and at most one visible vertical scroll owner; and source inspection found no repository, adapter, CLI, network, calculation, classification, reconciliation, mutation, or action execution in the Ledger TUI package.

Initial focused gates passed 13 tests, Ruff, ty, and basedpyright. Post-remediation review re-probed every finding at its production call site and its independent regression assertion.
