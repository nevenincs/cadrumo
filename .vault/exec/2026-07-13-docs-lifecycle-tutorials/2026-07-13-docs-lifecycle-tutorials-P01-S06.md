---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:006310c0fbf3b05c3a9d14929220fac394a1b15962d773b1304e99a82546fbb3'
step_id: 'S06'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Land the extracted explanation-page signals tightened on their receiving pages (verify-state taxonomy, revision immutability, xlsx-vs-Sheets, fingerprint purpose, reconcile scope, mixed-cost splitting, import readiness)

## Scope

- `docs/how-to/verification-reports.md docs/how-to/filing-spine.md docs/how-to/review-with-google-sheets.md docs/how-to/file-at-aeat.md docs/how-to/reconcile.md docs/how-to/classify-transactions.md docs/how-to/import-bank-statements.md`

## Description

- `verification-reports.md`: add the "This page covers the ..." opening plus
  the three-question verify semantics, the external cross-draft checks
  (clean-state guard, IVA-balance reconciliation, carried-figure revision
  stamps), and the tightened "verifying is NOT acceptance / NOT an upload
  guarantee / NOT a deadline check" list, extracted from
  `explanation/editing-and-verifying.md`.
- `filing-spine.md`: add the opening paragraph, the revision-immutability
  guarantee (content-identified, earlier revisions untouched, compare and go
  back), and the protective rationale for export refusing a plain draft.
- `review-with-google-sheets.md`: add the opening paragraph and the
  xlsx-is-a-keepsake vs Sheets-is-the-review-surface distinction, extracted
  from `explanation/reviewing-and-exporting.md`.
- `file-at-aeat.md`: add the opening paragraph and expand the SHA-256 line
  with the fingerprint's purpose (re-derive and compare later).
- `import-bank-statements.md`: add the opening paragraph and expand the
  preflight section with the five-item readiness checklist, extracted from
  `explanation/from-records-to-figures.md`.
- `classify-transactions.md`: add the three-source mixed-cost-split framing
  (per-record percentage, category default, registered-facts ratio) to the
  mixed-use section.

## Outcome

Every extraction target named by the research now carries its signal at the
point where the user runs the command, phrased as tightened statements rather
than transplanted narrative. `reconcile.md` needed no change: the
reconcile-scope precision (four header fields, never a box) was already
present on the how-to page.

## Notes

The explanation pages still carry the source prose; P01.S07 trims them now
that every actionable fact has a confirmed home.
