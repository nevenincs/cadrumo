---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S30'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Make secure-object namespace enumeration stream decrypted rows instead of materialising and sorting the full set

## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`

## Description


- Audit the enumeration path: `SecureObjectRepository.iter_records_with_failures` already streams the raw SQL scan (`stream_results=True`, `yield_per`, `ORDER BY object_key`, per-row decrypt, fault-isolated).
- Trace the materialise+sort named by M8 to `SecureBoundRepository.iter_ids` / `iter_records` (`envelope/_secure_repository.py`): both buffer every decrypted row and `sorted(...)` in Python.
- Audit the ~12 enumeration consumers and the contract test for order-dependence.

## Outcome

STEP COMPLETE — resolved as ordering-interface-segregation.

`SecureBoundRepository.iter_records` / `iter_ids` now stream each decrypted
payload/id straight from `list_records` without the second buffer or the Python
`sorted(...)` the M8 finding named. Peak memory halves (one fail-closed buffer
instead of buffer-plus-sort-buffer) and the O(n log n) sort leaves the hot
enumeration primitive.

The ordering decision was resolved, not dodged: the primitive yields in storage
order (the `object_key` digest order), and the few consumers that document a
sorted result opt in explicitly — `filing.list_draft_ids` / `iter_drafts`,
`justificante.list_csvs` / `iter_justificantes`, `submission.list_submission_ids`,
and `filing-history.list_modelos` each gained an explicit `sorted(...)`. This is
strictly better design than the old global sort: the repository no longer imposes
a sort cost on every consumer; order is a per-consumer concern. Consumers that
already re-sort (`_iva_remote_state`, `_rule_repository`, observations decisions)
or self-sort (`submission.iter_submissions`) are unaffected.

The **fail-closed contract is preserved unchanged**: `list_records` still scans
the whole namespace and raises `SecureObjectUnreadableError` before a full
consumption yields a readable subset past a corrupt row (the earlier worry that
streaming would weaken this was avoided by streaming *through* `list_records`
rather than bypassing it). The contract test now compares order-independently.

## Notes


The earlier deferral judged this net-negative on the assumption that relaxing the
ordering contract churned consumers for no gain. Re-framed under the completion
mandate, the right design is interface segregation of ordering — net-positive, and
the consumer churn was four explicit `sorted(...)` opt-ins, all behaviour-
preserving. Gates: storage suite 847, filing/justificante/submission/history 125,
lifecycle/evidence/observations/ledger 351 — all green. Committed as
`perf(secure-objects): stream SecureBoundRepository enumeration in storage order (S30)`.
