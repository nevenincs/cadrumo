---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:05c9324f56feed9dec45462190e731615964b30c778874b1a384be0ed5dca90c'
step_id: 'S11'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Correct the stale exclusion rationale on modelo_reconcile_bytes. Its docstring justifies withholding declaracion reconciliation on the bytes path because the only authenticated live-capture flow today captures justificante snapshots and never a filed declaracion. The filed-history pull falsifies that: it captures filed declaracion observations with per-casilla values and stores their artefact bytes. Every fact in the sentence still parses, which is why it survived review - the sentence did not change, the world did, and the next reader takes it as the current rationale for an exclusion that no longer holds. Gate: the corrected prose states what is true of HEAD at the time of the change rather than restating a premise, and a grep of the module for prose describing the old state returns nothing

## Scope

- `src/cadrumo/application/modelo/_reconcile.py`

## Description

- Read the sibling row (`P01.S12`) and the module it landed
  (`_pulled_filing_reconcile.py`) before touching prose, since the correction
  needed to name what actually replaced the old exclusion, not merely negate
  it.
- Rewrote `modelo_reconcile_bytes`'s docstring to drop the categorical "the
  only authenticated live-capture flow captures justificante snapshots, never
  a filed declaración" claim and state the current truth: filed-history pull
  now captures filed declaración observations with per-casilla values and
  their own artefact bytes.
- Named the ACTUAL current reason the function still refuses a `DECLARATION`
  source kind: it accepts only caller-uploaded, justificante-shaped evidence,
  and a pulled declaración never needs uploading — its casillas are already
  reconciled against the taxpayer's own local calculation by
  `pulled_filing_divergence_findings`, over the same bucket the sweep already
  populated.
- Left the function's behaviour unchanged: the `DECLARATION` branch still
  refuses with `ReconciliationDeclaracionSourceUnsupportedError`. The row
  asks for a prose correction, not a new reconcile path.

## Outcome

`grep -n "only authenticated live-capture\|never a filed declaraci" src/cadrumo/application/modelo/_reconcile.py`
returns nothing. The corrected docstring cites the live channel that makes
the old exclusion moot by name rather than leaving a bare negation, so a
later reader lands on the actual current mechanism instead of an absence.

`ruff check` / `ruff format --check` on the touched file: clean.

## Notes

Pure docstring change; no behaviour, no test, no registry data touched. The
shared refusal message (`application.modelo.errors.reconcile_declaration_unsupported`)
was read and left untouched: it is raised from four sites for different
reasons (enrolment gaps as well as this bytes-path restriction), so
rewording it was out of this row's scope and would have required auditing
all four call sites' fitness for a new wording.
