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

## Review follow-ups — actioned

- **MEDIUM-1 — bucket event on the stamp. RESOLVED.**
  `register_capture_as_filing_evidence` now emits a `MODELO_LIVE_EVIDENCE_STAMPED`
  bucket event (work unit, evidence kind, reference id, snapshot id), and the
  stamp is wired into the capture flow per the ADR's "in the same flow" wording —
  best-effort, a no-op when the period has no current in-app filing. Landed in the
  follow-up commit `02fba781b`; tests prove the stamp + event on a filed period
  and the skip on an unfiled one.
- **MEDIUM-2 (operator surface). RESOLVED** — see the P04 summary: the capture
  verb now stamps in-flow, and `aeat app modelo reconcile --from-capture` reaches
  the reconcile payoff.
