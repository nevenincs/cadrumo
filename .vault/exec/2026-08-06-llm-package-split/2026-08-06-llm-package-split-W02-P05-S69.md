---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:cc6bf557217266f43533cdfb774f18300362f1e97a63be9c13e948b4c153da3a'
step_id: 'S69'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Add a caller-supplied idempotency key to evidence add deriving a clock-free id when one is passed, keeping the keyless path additive with its documented genuine-duplicate rationale, red if a keyed re-add over one blob still mints a second record and a second bucket event

## Scope

- `src/cadrumo/application/ledger/_evidence.py`

## Description

- Derive a clock-free evidence id from the bucket and a caller-supplied idempotency key.
- Branch evidence add on the key: a keyed re-add over one blob resolves to the existing record instead of minting a second.
- Keep the keyless path additive, with its genuine-duplicate rationale documented rather than assumed.

## Outcome

A retry carrying the same key returns the existing record and emits no second bucket event. The keyless path is unchanged: two genuinely distinct evidence records over the same blob still both persist, because a taxpayer can legitimately hold the same document twice.

The id is clock-free on purpose. Folding a timestamp into identity means a retry at a different instant mints a different id, so the guard never fires and the retry double-writes -- which is the defect the guard exists to prevent, reintroduced by the id derivation itself.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_idempotency.py -m "unit or integration" -n 0
    5 passed in 0.29s

## Notes

RECONSTRUCTED RECORD. Written during a tracker reconciliation, not by the agent that executed the Step. Verified present and green at HEAD before the box was ticked, but the reasoning and the alternatives weighed live in the commit history, not here. See the tracker-reconciliation audit for why these records were recovered rather than authored at execution time.
