---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` Code Review

RELOAD-001 | HIGH | Rule application must not hide write failures as no-match
`apply_classification_rules` caught all exceptions from the transaction update path and reported them as `no_match`. Resolved 2026-05-27 by letting update, validation, and persistence failures propagate while preserving `no_match` only for transactions with no matching rule.

RELOAD-002 | HIGH | Wallet secure-storage tests must not use valid-looking taxpayer identifiers
The wallet backend test used a plausible taxpayer identifier literal as synthetic input. Resolved 2026-05-27 by replacing it with a non-identifier synthetic reference and preserving the privacy assertions that raw taxpayer references are not emitted by stored reports or secure SQL bytes.

RELOAD-003 | HIGH | Wallet privacy guard must cover implementation code and CIF-shaped identifiers
The initial static guard covered wallet-named test/source files but not the live application module that contains the wallet reload and capture functions, and it matched DNI/NIE-shaped identifiers without CIF-style entity identifiers. Resolved 2026-05-27 by scanning the live application module and extending the identifier detector to personal and legal-entity Spanish taxpayer shapes.

RELOAD-004 | HIGH | Filed-history-only fallback must not become filing-grade IVA wallet authority
The reconciliation path classified missing direct wallet/cartera plus AEAT filed-history recurrence as `filed_history_only` but left the decision non-blocking, allowing Modelo 303 calculation to prefill prior compensation from fallback evidence. Resolved 2026-05-27 by making `filed_history_only`, missing-wallet local recurrence, and stale-wallet local recurrence blocking decisions; the real Modelo 303 engine now requires an explicit taxpayer override before using the fallback amount.
