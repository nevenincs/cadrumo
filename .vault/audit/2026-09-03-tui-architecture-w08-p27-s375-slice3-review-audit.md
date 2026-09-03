---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:3c89f860cb7fa9c4e5c44b12b53a7d1601102174db227a42a5d519cdd926091a'
related:
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
  - '[[2026-08-11-tui-architecture-plan]]'
---
# `tui-architecture` audit: `W08.P27.S375 slice 3 independent review`

## Scope

Independent review of the live evidence and reconciliation slice, including controller, routes, presentation models, screens, tests, and all shipped locale copy. The review traced evidence metadata sensitivity, catalogue authority, mutation admission, reconciliation source truth, affected-declaration meaning, asynchronous state transitions, Escape and repeated-submit behavior, refusal and stale-authority handling, semantic identity and focus, eighty-column geometry, one-scroll ownership, forbidden dependencies, and whether tests prove production invariants.

## Findings

### reconciliation-selection-is-positional | high | Open: a reordered visible row can submit a different visible pair

`LedgerReconciliationScreen.on_data_table_row_selected` reads `event.cursor_row` and indexes `controller.projection.invoice_reconciliations` at that position even though every rendered row already has a semantic transaction/invoice row key. If DataTable presentation order changes, selecting a visible row can therefore prepare another visible pair. Controller admission does not contain this defect because the wrongly indexed pair is also present in the projection. The current single-suggestion test necessarily passes and cannot distinguish selected-row identity from projection position.

Resolve this by deriving the selected pair from the semantic row key or an immutable row-key-to-pair map, never from cursor position, and add a two-row adversarial test that changes presentation order before selecting a row and asserts the exact visible pair reaches the injected link door.

### reconciliation-source-facts-are-reclassified-or-dropped | medium | Open: presentation invents match classes and suppresses canonical reconciliation meaning

The reconciliation screen synthesizes `Full` when both `amount_match` and `counterparty_match` are true and `Partial` otherwise. That grouping is frontend-owned policy: it collapses materially different states and ignores the application projection's canonical `score`. The inconsistencies table likewise drops the application-owned `direction`, leaving only two opaque reference prefixes and no visible description of which side is missing. This is presentation logic deciding or withholding domain meaning rather than faithfully formatting the injected immutable projection.

Resolve this by rendering application-owned reconciliation facts with localized labels, including enough boolean/score and direction meaning to distinguish the projected states. If a Full/Partial classification is a real product concept, move it into the application projection first. Add exact multi-state tests so the UI cannot silently collapse distinct source rows.

### reconciliation-copy-tests-are-partially-vacuous | low | Open: locale and source-truth assertions do not prove reconciliation meaning

The local-versus-AEAT test merely checks that the rendered page contains `AEAT`, and the all-locale test compares only the evidence title. Those assertions would pass for misleading AEAT copy and do not exercise reconciliation terminology. The single-row fixture also cannot expose positional identity or collapsed match states. The live locale files are genuinely authored and the English banner is explicit, so this is a proof gap rather than a current translation defect.

Add exact assertions for the local-only/AEAT-separation message and representative reconciliation labels in every shipped locale, plus multiple reconciliation states and inconsistency direction.

## Recommendations

Hold final review until the high and medium findings are remediated and their adversarial tests pass. The low proof gap should close in the same test update because it is the durable regression guard for the source-truth fix.

Positive findings: evidence rendering limits itself to safe manifest presentation facts and does not expose provider locators, hashes, linked invoice identities, or full attachment identities; both evidence and link capabilities are validated against the real injected application catalogue; link submission admits only a visible injected transaction/invoice pair and validates returned identity; affected declarations visibly separate Modelo, period, and changed/removed counts; the page explicitly states that it shows local Ledger evidence and that AEAT Sync is separate; absent dependencies, unavailable applications, and still-deferred routes produce typed refusal; workers disable controls, reject in-flight Escape and repeated submission, preserve generic localized errors, and restore semantic focus; all four locales contain real authored strings; eighty-column compositor checks show no horizontal table scroll and one page scroll owner; and the slice imports no adapters, CLI, file readers, action implementations, or concrete services.

Focused gates: 40 Ledger tests passed with all markers enabled; Ruff passed; ty passed; basedpyright reported zero errors and zero warnings. These gates do not discharge the open findings because the current fixtures do not exercise reordered multi-row selection or the missing source distinctions.
