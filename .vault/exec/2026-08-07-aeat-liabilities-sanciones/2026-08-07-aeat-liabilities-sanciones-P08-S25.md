---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:34cad048a7548ebbba0f8c8037b7e7c40cbe159007e3dc438babe8dc81d5e805'
step_id: 'S25'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Add the frozen PersistedNotificationDocument model carrying certificado_id, the AttachmentStore attachment id, pdf_sha256, source_url and fetched_at under STRICT config, exposing NO filesystem path field of any kind, verified by a model validation unit test asserting the field set and that no field name or value carries a path

## Scope

- `src/cadrumo/application/live/_notification_documents.py`

## Description

- Gate the custody record's exact persisted field set, so a field added later has to be
  classified rather than defaulted silently through the save and the load.
- Gate the absence of any filesystem-path field, by NAME and by ANNOTATION, walking union
  members so a path hidden inside an optional is caught too.
- Prove both detectors non-vacuous against a probe model declared in the test, rather than
  by breaking the record.
- Gate that the three re-store classification sets partition the field set exactly and are
  pairwise disjoint, which is what makes comparing five fields equivalent to comparing ten.

## Outcome

The model itself was already correct at HEAD: frozen, STRICT config, no path field. The gap
was that nothing asserted it, so the property held by accident of the current author rather
than by contract. The record now carries a shape gate keyed on the property: the no-path
assertion iterates the declared fields and their annotations rather than counting anything,
and the field set is written out as a set so the next author is asked which side of the
re-store match their field falls on instead of being asked to bump a number.

Modified files:

- `src/cadrumo/application/live/tests/test_notification_documents_service.py` (new)
- `src/cadrumo/application/live/tests/_notification_document_support.py` (new)

Both gates were proved to bite by widening the record at runtime from outside the
repository: a probe adding a defaultable field reds the field-set gate, and one adding a
path-annotated field additionally reds the annotation gate. No tracked file was edited to
run the proof.

## Notes

The shared fixture module is new because the served-PDF builder was about to exist twice.
It is extracted from the custody suite rather than copied, and the custody suite now imports
it, so there is one construction of the document both suites read.
