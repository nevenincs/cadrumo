---
tags:
  - '#reference'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:56e7c729dd84d56ffd0eb221840aeb52bdb1d717a6c40a96bc4a01f2458bcd29'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
---

# `m303-carry-reconciliation` reference: `M303 S16 submitted-file extraction Notice route`

Trace of the submitted-file layout-refusal diagnostic from the authenticated
Sede capture through the live capture reports and the CLI envelope.

## Summary

The Sede submitted-file projection makes a structured `SedeParseError` whose
context includes modelo, revision, period, expediente, artefact digest and the
parser reason. Its sole production catcher records `str(exc)` under
`submitted_file_extraction_error` on `FiledDeclaracionObservation`; it then
leaves the declaration-PDF fallback unchanged.

`_CaptureAccumulator` is the single persistence funnel for single, bulk and
source filed capture. `FiledCaptureEvidenceTally` is consequently the right
internal transport for a typed warning derived only when that recorded metadata
exists. It is not a result payload: entrypoints forward those notices through
the shared envelope channel, preserving the parser reason and the filing
coordinates.

The offline browser fixture cannot safely reach the submitted-file fetch because
the API request bypasses Playwright route interception. The valid local proof is
therefore an exporter-produced M303 fichero truncated into the real parser
refusal, followed by the production encrypted capture accumulator, live notice
relay and JSON envelope writer. A successful exporter-produced fichero supplies
the corresponding no-notice control.
