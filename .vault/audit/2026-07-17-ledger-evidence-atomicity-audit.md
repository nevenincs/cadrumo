---
tags:
  - '#audit'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:d7209edca112faf550c51478b723bba4992a52bc43fadfb4d5f6792345e5cde2'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
  - "[[2026-07-17-ledger-evidence-atomicity-adr]]"
  - "[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]"
---

# `ledger-evidence-atomicity` audit: `ledger evidence durable-layer continuous-gate review`

## Scope

Continuous-gate review of the ledger-evidence-atomicity durable layer landed by phases P01 and P02: the single evidence-write authority (attach as the sole evidence mutation, invoice link as an atomic invoice-only writer) and the atomic split persistence path. The review confirms the write-authority and atomicity guarantees and flags two low-severity gaps where a bypass or an unchecked id assumption could defeat them.

**Status: PASS.** The evidence-write authority and atomic split persistence hold. No Critical or High findings.

## Findings

### evidence-write-authority | confirmed | Attach is the sole evidence mutation and invoice link is atomic

Generic manual-field updates refuse all evidence fields, evidence catalogue and provenance mutation are reserved for attach, and invoice linkage is a single atomic invoice-only writer. A failed attach or link leaves the transaction, evidence catalogue, provenance, and event history unchanged.

### low-1-builder-bypass-bulk-classify | low | The one-evidence-writer guard sits on the wrapper, not the builder, so bulk_classify can bypass it

The single-evidence-writer guard is enforced at the wrapper rather than at the transaction builder, so the bulk-classify path can reach the builder and mutate evidence fields outside the attach authority. Remediation: move the guard to the builder — the builder asserts the evidence set equals the current evidence unless the `_evidence_authority` marker is present, OR the `BULK_CLASSIFY_ALLOWED_COLUMNS` set is proven to never intersect the evidence fields. Relevant sites: `src/cadrumo/application/ledger/_actions_manual.py` around line 607, `src/cadrumo/application/ledger/_actions_classification.py` around line 243, and `src/cadrumo/application/ledger/_models.py` around lines 789-802. Enrolled as a gated step under plan phase P03.

### low-2-split-child-id-stability | low | split_transaction_with_classified_children assumes child id stability without asserting it

`split_transaction_with_classified_children` assumes the classified replacement child keeps the same transaction id as the bare child it derives from, but does not assert it; a divergence would silently misattribute evidence and provenance. Remediation: add an explicit assertion that raises when `replacement.transaction_id != bare_child.transaction_id`. Relevant site: `src/cadrumo/application/ledger/_actions_split_merge.py` around lines 370-384. Enrolled as a gated step under plan phase P03.

## Recommendations

Close LOW-1 by relocating the one-evidence-writer guard to the builder (or proving `BULK_CLASSIFY_ALLOWED_COLUMNS` disjoint from evidence fields) so bulk-classify cannot bypass the attach authority, and LOW-2 by asserting split child-id stability so a divergence raises rather than silently misattributing evidence. Both are enrolled as tracked steps under phase P03; neither blocks the PASS verdict.
