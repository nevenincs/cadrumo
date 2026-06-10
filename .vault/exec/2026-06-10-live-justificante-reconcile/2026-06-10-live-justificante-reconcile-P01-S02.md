---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
step_id: 'S02'
related:
  - "[[2026-06-10-live-justificante-reconcile-plan]]"
---




# Author the JustificanteCaptureSnapshot payload (modelo via core Modelo enum, filing_year, period, expediente_id, csv, pdf_sha256, pdf_bytes, official source_kind, lifecycle), object-key, content-addressed id, repository and SnapshotService hooks mirroring Borrador100.

## Scope

- `src/aeat/application/live/_justificante.py`

## Description

- Author `JustificanteCaptureSnapshot` payload (modelo via core `Modelo`,
  filing-year/period axis, expediente/csv provenance, raw-bytes `pdf_sha256`,
  base64 `pdf_base64`, official `source_kind`, three-state lifecycle).
- Add object-key, content-addressed id derivation, repository, and
  `JustificanteCaptureSnapshotService` mirroring the Borrador100 hooks.
- Register the `JustificanteCaptureSnapshotNotFoundError` ErrorCode and its
  four-locale message leaf (co-requisites for the module to import).

## Outcome

Module imports clean; error-hygiene, namespace, and locale gates green. Landed
as commit `a3810828f`.

## Notes

The PDF is persisted as a base64 `str`, not a pydantic `Base64Bytes` field:
`Base64Bytes` decodes its input on validation, which would corrupt raw binary
passed at construction. Storing the explicit base64 string round-trips
losslessly through the JSON envelope. No scaffolds left.
