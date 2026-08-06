---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:523f21bcbba95564cc9a3b9f7701b470edb0c5129d749d6a6ab1da6a4f2144a9'
step_id: 'S74'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Decide wire-or-delete for each of the four dormant categories rather than leaving the declared reason as a permanent state, recording the decision and its rationale for status-cache, storage-backup, inbox, and inbox-pdf, plus the fifth item status-cache's unreferenced companion field cadrumo_status_cache_ttl_s, which a peer lane has re-verified dead by the string-constant method alongside all four categories and recommends deleting together with status-cache

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Decide wire-or-delete for each of the four dormant categories rather than leaving the declared reason as a permanent state, recording the decision and its rationale for status-cache, storage-backup, inbox, and inbox-pdf, plus the fifth item status-cache's unreferenced companion field `cadrumo_status_cache_ttl_s`.

## Outcome

Decided: delete all five. Landed in commit `9a0ff23040` ("delete four writer-less taxonomy members and their settings"). Re-confirmed dead at fresh HEAD by the string-constant method — the same evidence shape the liveness gate itself uses (per R9's amendment), not only attribute-consumption, which is the weaker method that produced a false positive elsewhere in this campaign (the IVA read-evidence pair). Every hit for all five field names was the declaration site itself, nothing else. Deletes the four `StorageCategory` members, their `_location(...)` declarations, and `cadrumo_status_cache_ttl_s`. Verified independently at committed HEAD: zero `StorageLocation` declarations carry a non-`None` `dormant_reason` today, and `status_cache_ttl` does not appear anywhere in `config.py`.

## Notes

This lands the decision this Step's own text anticipated ("wire-or-delete") as delete, for all five items, in one commit — landed and independently verified in the same session the Step was authored.
