---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:28424d48d23dd5b19e210975f5a9c4489cf8a4d175d980b5f700c937d08c85fe'
step_id: 'S01'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Add a csv-equality check recovering the CSV from the justificante_pdf artefact source_url via extract_csv_from_url, fold a resolution failure into the existing swallowed-outcome shape, and drop the now-signature-invalid expediente_id argument in the same change

## Scope

- `src/cadrumo/application/live/_filed_observation_persistence.py`

## Description

`_parse_matching_filed_justificante` was the one site with no receipt-namespace
check. The CSV it needs is not unavailable there: the capture resolves it from
AEAT's cotejo redirect, builds the document URL around it, and persists that URL
verbatim as `FiledDeclaracionArtefact.source_url`.

## Outcome

Recovered the CSV with `extract_csv_from_url(str(artefact.source_url))` and
compared it case-folded against the freshly parsed `justificante.csv`. A
`SedeParseError` from a URL carrying no usable CSV is folded into the existing
swallow-and-report shape rather than propagating, because this function runs
inside a loop over every artefact and one malformed URL must not abort a whole
enrollment. The now-signature-invalid `presentation_id=observation.expediente_id`
argument was dropped in the same change, so the site never lands checked more
weakly than it started.

Documented on the function why the comparison means anything: two distinct
channels are compared, and a `source_url` built from the receipt's own CSV - or
from a period-level template - would collapse it into a value checked against
itself that passes unconditionally while still reading as a real check.

## Verification

Covered by the S06 and S12 tests plus two new refusal tests (CSV mismatch, and a
source URL with its query stripped). Gate proven to bite: an out-of-repo `-p`
plugin made the comparison vacuous under `-n0`, and five tests went red including
the discrimination test.

## Notes

No persisted field was added and no persistence boundary changed; `source_url` is
an existing round-tripped field.
