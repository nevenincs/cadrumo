---
step_id: S99
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-30-identity-primitives-adr]]"
---

# core-authority W12.P29.S99 step record

## Step

Declare `EvidenceId` alias in `core/identity/_evidence.py`, re-export through `core/identity/__init__`, delete the `application/evidence/_ids.py` declaration, and update all callers. (RELOC-038, Rule 1)

## Status

BLOCKED — relocation not justified by Rule 1 cross-consumption criterion.

## Blocking rationale

Pre-execution cross-consumption audit found zero consumers of `EvidenceId` outside
`application/evidence/`. The one domain reference that the bare-str detector surfaced
(`domain/transactions/_models.py:452 TransactionEvidenceProvenanceEntry.evidence_id`)
carries a different constraint shape (`min_length=1, max_length=128`) that does not
match `EvidenceId` (hex-64, exactly 64 chars). That field cannot be typed to
`EvidenceId` regardless of where EvidenceId lives.

The identity-primitives ADR Rule 6 explicitly placed `EvidenceId` in
`application/evidence/_ids.py`. Rule 1 clause (a) requires cross-layer consumption
to trigger promotion. No such consumption exists.

Additionally, `application/ledger/_evidence.py` uses `evidence_id` values minted as
`uuid.uuid4().hex[:16]` (16 chars) in test contexts, confirming the field does not
carry the hex-64 shape that `EvidenceId` enforces.

## Follow-up condition

If a future surface outside `application/evidence/` consumes `EvidenceId` and that
surface carries a confirmed hex-64 content-addressed shape, Rule 1 clause (a) is
satisfied and the relocation becomes mandatory.

## Files touched

None.
