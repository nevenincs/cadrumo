---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W09.P46` summary

P46 completed the full post-Wave-1 period-token audit and converged every confirmed generic survivor onto typed or domain-specific authorities. The result preserves legitimate legal and registry distinctions while eliminating duplicate parsing, date, ordering, and display policy.

- Modified: `src/aeat/core/_period.py` and `src/aeat/domain/period.py`
- Modified: registry previous-filing offset and calculation-runtime modules
- Modified: verification, filing, modelo projection, workflow, IVA, prorrata, and calculation-sheet consumers
- Modified: CLI overview, ledger, and MCP prompt/completion surfaces
- Created: IVA M303 settlement policy module and focused real-behavior regression coverage

## Description

The phase began with S169's RAG-grounded matrix, which separated canonical adapters and legal wire grammars from genuine competing authorities. It identified calculation-date drift, stale workbook-layout risk, invalid MCP vocabulary, duplicated prior-quarter/ordinal/order/settlement rules, and reversed typed-period display.

The completed repairs establish `calculation_filing_date` for calculation contexts while retaining strict range helpers; protect Sheets layouts with a compiler-version gate; use core typed quarter and declaration projections; centralize IVA compensation ordering and M303 settlement timing; derive MCP completions from the finite core vocabulary; and use canonical `Period` display for human CLI text. The current M303 registry has no annual `0A` revision, so the settlement policy explicitly retains fail-closed encrypted ingress while preserving typed future-annual precedence.

Every completed step received independent review. Evidence includes real encrypted-store Modelo 202 and M303 journeys, bundled M369 exterior registry snapshots, actual Sheets export/pull/compute paths, MCP integration handlers, and CLI rendering. Focused suites and scoped Ruff checks passed for each repair; reviewer-discovered oracle gaps and ordering regressions were repaired before closure.
