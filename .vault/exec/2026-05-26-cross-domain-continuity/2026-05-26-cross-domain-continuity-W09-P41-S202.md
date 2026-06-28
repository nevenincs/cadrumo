---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S202'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# audit stored-data drift taxonomy semantic gap

## Scope

- `class lives under errors.refused.* REFUSED category but stored-data drift is semantically an integrity failure not a safety refusal`
- `decide whether to rename and re-emit telemetry or document the semantic exception`
- `src/aeat/core/errors/registry/_entrypoints.py`

## Description

Audited the current category assignment for
`CliStoredDataValidationBoundaryError` in
`src/aeat/core/errors/registry/_entrypoints.py`.

## Outcome

Already resolved. The class is registered with
`category=ErrorCategory.INTEGRITY` and
`code="INTEGRITY_STORED_DATA_VALIDATION_BOUNDARY"`. The plan Step's
concern — "class lives under errors.refused.* REFUSED category but
stored-data drift is semantically an integrity failure" — does not
match the current registry shape; the category is INTEGRITY, the
code is integrity-namespaced, and the message_key
`errors.storage.stored_data_validation_boundary` is in the storage
namespace (not the refused namespace). No semantic gap to close.

## Notes

The matching sibling registrations in `_application.py:1072,1094`
and `_domain.py:1996,2007` also use INTEGRITY + the storage
message-key namespace. The cross-domain consistency is already in
place.

