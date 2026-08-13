---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ba9e5ce67a32acb9d1b28034d74ea1598c0412c99e9636793baf763e8e84ada1'
step_id: 'S18'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype the two bare-`str` CSV fields onto `AeatCsv`

## Scope

- `src/cadrumo/application/live/_justificante.py`

## Description

- Retype `JustificanteCaptureSnapshot.csv` from `str` carrying an inline
  `min_length=8, max_length=32` to the canonical alias, deleting the inline
  bound as the duplicate authority it was.
- Retype `_JustificanteCaptureRequest.csv` from an entirely unconstrained `str`
  to the same alias.
- Add the alias to the module's existing `core.identity` import.

## Outcome

Both pydantic CSV fields in `src/cadrumo/application/live/_justificante.py` now
name the canonical alias. The snapshot field's inline bound restated exactly
what the alias declares, so removing it collapsed two statements of one
contract into one; the request field previously stated nothing, so it gained
both the bound and the shared normalisation.

The narrowing is safe at both sites because the producer is already
alias-validated: the live capture flow passes the parsed sede reference's own
CSV field, which the sede schema types on the same alias, into the capture
service.

Landed as one commit, staged through the HEAD-anchored own-only route because
the file carries a concurrent peer's in-flight error-taxonomy work. The staged
set was three added and three removed lines in this file alone.

Focused verification: the justificante-selected live tests pass. The single
failure in that selection is the live-gate test that requires the live-tests
environment opt-in, which is unrelated and fails identically without this
change. Lint, format and type checks are clean on the file.

## Notes

Two non-field CSV occurrences in this module were deliberately left bare, and
the reasoning is recorded rather than assumed.

The capture service's `capture` method parameter stays `str`. A plain
function's annotation runs no validator, and this parameter is precisely the
boundary at which an un-normalised value is still acceptable: the request model
it feeds normalises and validates immediately downstream. Annotating it with
the alias would assert the caller had already produced the canonical form,
which is the opposite of what the boundary promises.

The private helper comparing existing evidence reference ids against a capture
CSV also stays bare, because the reference id it receives is a generic external
evidence reference, not necessarily a CSV.

Left for a successor rather than widened here: this module compares CSVs with
inline strip-and-uppercase at three sites rather than routing through the
shared comparison form. Those expressions are inside hunks a peer is actively
rewriting, and the row scopes to fields, so they were not touched. They are the
same defect class the calendar-evidence row addresses.
