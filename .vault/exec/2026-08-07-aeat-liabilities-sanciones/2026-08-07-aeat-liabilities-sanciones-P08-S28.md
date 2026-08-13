---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:129a9a5deee774219b10e950afe33c9d1091a6c82853bec868c69d5618546f32'
step_id: 'S28'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Write the strict roundtrip test against a real SecureObjectRepository, real key provider, real SQLite engine and real AttachmentStore, populating every defaultable field non-default and asserting strict pydantic equality, then the anti-tautology proof deleting a persisted field on disk and asserting reload refusal

## Scope

- `src/cadrumo/application/live/tests/test_notification_documents_service.py`

## Description

- Extended the strict encrypted roundtrip to close the one field it left at its default: `parse_refusal`, mutually exclusive with `sancion` by construction, is now proven to survive save/load at a non-default value on the unreadable-document record via a strict `loaded == record` equality check.
- Added the matching anti-tautology proof: `parse_refusal` carries a default, so deleting it from the decrypted on-disk payload does not raise; the proof instead asserts strict inequality between the persisted and reloaded records, and that the reload silently re-defaults to `None`.
- Updated the module docstring to describe the two-record strategy: `sancion` and `parse_refusal` cannot both be populated on one record, so full defaultable-field coverage is proven across the sanción roundtrip and the refusal roundtrip together.
- Confirmed both proofs are load-bearing with runtime monkeypatches driven from outside the tracked tree: one simulating a save that genuinely drops `parse_refusal` (reds the extended roundtrip equality check), one confirming the anti-tautology test's inequality assertion depends on the mutation actually running (reds without it).
- Ran the real-adapter test suite, `pytest --collect-only`, and the docs build gate; all green.

## Outcome

Closed. The strict roundtrip now exercises every defaultable field on `NotificationDocumentRecord` at a non-default value at least once, and `parse_refusal` has its own anti-tautology proof alongside the three pre-existing ones for `attachment_id`, the nested sanción figure and `byte_size`.

## Notes

The originating Step row names `test_notification_documents_service.py` as the scope file. That file already exists and now holds SERVICE SEMANTICS (field-set gate, delegation, idempotency) added by a prior Step; the roundtrip and its anti-tautology proofs live, and stay, in `test_notification_document_custody.py`, where the whole roundtrip suite already lived. Creating a second copy there would have been the exact duplication this campaign's discipline forbids, so this record's actual scope is the custody file, not the one named in the row.
