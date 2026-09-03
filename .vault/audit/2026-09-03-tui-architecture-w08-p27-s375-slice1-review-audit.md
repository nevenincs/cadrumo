---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:c9c7279ac19473cb55fe9face463ff6d636d626e88845ad7c21d281f5357a430'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `W08.P27.S375 slice 1 independent review`

## Scope

Independent read-only review of the first `W08.P27.S375` Ledger workspace slice against the accepted navigation join and the live application-owned Ledger projection. Scope covered the exact route catalogue, injected projection and admission state, deferred destinations, overview hierarchy, entries and review source fidelity, redaction, action identity authority, semantic focus, Escape behavior, localization, eighty-column geometry, scroll ownership, forbidden authority acquisition, and whether focused tests prove those claims independently.

## Findings

### locale-fallback-masquerades-as-i18n | high | All non-English locales render English defaults while the locale test remains green

Every production label calls `ledger_copy` with a `tui.ledger.*` key and an English default, but none of those keys exists in any shipped locale catalogue. Spanish, Catalan, and Hungarian therefore render the English fallback rather than real localized copy. The parameterized locale test cannot detect this: it checks only that unresolved keys and internal enum spellings are absent, conditions satisfied by the English defaults, and never asserts locale-specific expected copy or that catalogue lookup succeeded. This is an explicit product-contract failure and a self-fulfilling test.

### unmeasured-counts-render-as-zero | medium | Deferred and unmeasured areas present zero as if it were an observed count

The application projection deliberately marks Import and Evidence `UNMEASURED`, yet `populate_navigation` and the overview quality table render `item_count` unconditionally. The resulting rows say â€œNot measuredâ€� beside `0`, conflating unavailable measurement with a proven empty result. Render an unavailable count marker or omit the count whenever status is unmeasured; add a semantic assertion that no zero is shown for those rows.

### review-filter-contradicts-projected-rows | medium | A screen labelled pending review accepts and displays reviewed entries

The review screen states â€œFilter: all pending review rowsâ€� but renders every `review_transaction_ids` member without a pending-state guarantee. The focused fixture places a `reviewed` entry in that tuple and the test intentionally selects it, so the suite currently proves the contradiction rather than catching it. Either the application contract must guarantee and validate the pending subset or the TUI must use copy that truthfully describes the application-owned queue; the test must not manufacture a reviewed row under a pending-only label.

### review-action-is-frontend-declared | medium | Review action authority is duplicated as an unchecked TUI literal

The controller constructs `ActionReference(action_id="operator.ledger.review")` locally, and the TUI row model validates it against the same hard-coded string. Neither site consults the canonical application action catalogue, so both tests and implementation can agree while the actual catalogue changes or removes the action. Bind the read request to an application-declared or catalogue-validated action reference and test parity against that independent authority.

## Recommendations

Hold slice 2 until the high localization defect and the three medium semantic-authority defects above are corrected with independent regression tests. No route or architecture decision needs reopening.

The remainder of slice 1 is structurally sound: the route catalogue covers the seven canonical areas exactly once; Overview, Entries, and Review are implemented while four deferred bodies resolve to typed truthful refusals; the outer factory retains the exact injected immutable projection and rejects the wrong destination context; entry payloads remain redacted; row and focus keys use semantic transaction identities; Escape posts a parent-return request rather than terminating the application; the eighty-column compositor reports no horizontal overflow and at most one visible vertical scroll owner; and source inspection found no repository, adapter, CLI, network, calculation, classification, reconciliation, mutation, or action execution in the Ledger TUI package.

Focused gates on the reviewed tree: `pytest -m ''` passed 13 tests, Ruff passed, ty passed, and basedpyright reported zero errors and zero warnings. These green gates do not discharge the findings because the relevant assertions encode or fail to observe the defects described above.

