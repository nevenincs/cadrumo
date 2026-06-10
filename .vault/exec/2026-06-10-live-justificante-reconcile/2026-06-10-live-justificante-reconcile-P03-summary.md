---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
related:
  - '[[2026-06-10-live-justificante-reconcile-plan]]'
---

# `live-justificante-reconcile` `P03` summary

Phase P03 (official evidence and cross-period gate) is complete. Both Steps
landed with their gates green.

- Modified: `src/aeat/application/live/_justificante.py` (`register_capture_as_filing_evidence`)
- Modified: `src/aeat/application/calculations/_cross_period_clean_state.py` (verified-kinds)
- Modified: `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`
- Modified: `src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`

## Description

`register_capture_as_filing_evidence` (`S07`, commit `7b3cc0480`) parses a
persisted capture into a domain `Justificante` (reusing the P04 materialise +
parse helper), forces the receipt's `csv` to the capture's authoritative CSV so
the repository key and the filing-record `reference_id` are equal, registers it,
and stamps the work unit's current filing record with `AEAT_LIVE_CAPTURE`
external evidence plus `aeat_accepted=True`. `aeat_live_capture` is added to the
cross-period gate's `_JUSTIFICANTE_VERIFIED_EXTERNAL_EVIDENCE_KINDS`: a
live-captured signed PDF is the authentic receipt, so it clears
`MISSING_JUSTIFICANTE_VERIFICATION`. `S08` (commit `bb82fc51e`) proves a filing
stamped with `AEAT_LIVE_CAPTURE` plus its registered justificante clears the
blocker, while an `AEAT_CSV_REGISTER` kind still trips it; the stamp test proves
the filing is marked live-captured and refuses when no current filing exists.

The independent code review confirmed this safety-critical path is sound: the CSV
override reconciles a parse-vs-URL discrepancy in favour of the AEAT-authoritative
value (no false clearance of `MISSING_EXTERNAL_EVIDENCE_RECORD`), `aeat_accepted`
mirrors the `import_external_filing_evidence` sibling, the gate still requires a
loadable justificante, and the stamp is an in-place update of the already-filed
VIGENTE record (not a parallel write path, so
`composition-service-no-parallel-write-path` does not apply).

## Deferred follow-ups (formally deferred per campaign-close honesty)

- **MEDIUM-1 — no bucket event on the stamp.** `register_capture_as_filing_evidence`
  mutates the filing record without emitting a `BucketEvent`, unlike the
  `import_external_filing_evidence` sibling. Deferred: attaching official
  acceptance evidence should leave an audit-trail event; tracked as a follow-up
  before the stamp is wired to an operator verb.
- **MEDIUM-2 (shared with P04) — the stamp has no operator CLI surface yet.** See
  the P04 summary; the stamp and reconcile-from-capture are library seams pending
  a follow-up CLI increment.
