---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
---

# `live-iva-compensation-wallet` Code Review

FILED-HISTORY-DIVERGENCE-001 | MEDIUM | Local recurrence provenance must not be inflated into AEAT filed-history evidence

Resolved 2026-05-27. Review found that `local_recurrence` sources with modelo/year/period metadata were still expanded into `filed_history_observation`, which could make app-local prior filings look AEAT-backed. The implementation now derives filed-history evidence only from preserved AEAT source kinds and keeps the local recurrence channel separate.

FILED-HISTORY-DIVERGENCE-002 | LOW | Production bridge coverage must prove persisted source kind drives filed-history-only decisions

Resolved 2026-05-27. Review found isolated tests for source preservation and manual reconciliation classification, but no end-to-end path from persisted observation source kind through Modelo 303 reconciliation. A Modelo 303 engine integration test now exercises missing wallet/cartera evidence with persisted AEAT filed-history recurrence and verifies `filed_history_only` remains non-blocking and provenance-bearing.
