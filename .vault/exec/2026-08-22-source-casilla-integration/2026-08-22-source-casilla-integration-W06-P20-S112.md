---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:efb28ef103631382445e601660ae61c9165cb58cf0927a249ad8578ed0d262c0'
step_id: 'S112'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# regenerate and compare the canonical connectivity census after completed source slices, record capability-selector drift without adjudicating it, and hand the result to S113/S115

## Scope

- `.vault/exec/2026-08-22-source-casilla-integration/2026-08-22-source-casilla-integration-W06-P20-S112.md`
- `.vault/index/source-casilla-integration.index.md`

## Description

- Discover the canonical `dev.source_connectivity` generator and comparison
  commands, the census compiler, and the selector-assignment gate before exact
  symbol searches.
- Run the read-only canonical generator. It reports 476 discovered structural
  capabilities; it deliberately has no census-authoring command.
- Reproduce the helper-selector ratchet refusal: the frozen 265-member helper
  set has changed to 267 members, so its expected digest no longer equals the
  live digest.
- Compare the baseline introduced with the current census against the live
  syntax-derived helper inventory without changing the census. Hand these two
  additions to S113/S115 as unadjudicated identities, not as connected,
  rejected, or blocked census rows:
  - `calculation_helper:src/cadrumo/domain/calculations/registry/_temporal.py:revision_selection_coordinates`
  - `calculation_helper:src/cadrumo/domain/portals/_errors.py:portal_integrity_error`
- Inspect the raw 15-entry census for expiry metadata. On 2026-08-25 its only
  expiry date is 2026-12-31, so this regeneration exposes no expired census
  row. Its existing bounded follow-ups remain 2026-10-31 and 2026-11-30.

## Outcome

S112 is complete as regeneration and discovery evidence only. The authoritative
census is unchanged: its 15 entries, 17 explicit capability claims, and five
selector entries were neither edited nor reclassified. The canonical generator
reported 476 capabilities, but the live comparison refused the stale
`coverage.remaining-calculation-helpers` ratchet:

- baseline: 265 capabilities,
  `sha256:3ddcba1760dbb46f65c8a1edd558516c24edb093348516bc01f1da73969aaddb`;
- live: 267 capabilities,
  `sha256:3b827ccf9f7fd2c3b30a37f042e9ede32be236d0b4600c8e3a09dcebbfeeeb6a`.

The two added helper identities are a bounded, unadjudicated handoff to S113
and S115. Discovery is structural: it cannot infer an authoritative fact,
grain, secure owner, destination, lifecycle, or census disposition from either
helper. Therefore no digest update, candidate row, or disposition was silently
written in this step.

## Notes

- The canonical comparison cannot load its live registry authority while an
  unrelated TUI relocation has deleted
  `src/cadrumo/application/modelo/_work_review_projection.py` before its
  replacement is committed. This is external shared WIP, not a census change;
  the read-only generator and archive-backed helper comparison remain sound.
- A later S113/S115 owner must investigate and classify the two identities
  before any census digest or disposition changes. S112 deliberately does not
  perform that adjudication.
- Source-index regeneration initially deferred because it named uncommitted
  S226 reviewer documents. After their audit committed at `7564b7a315`, the
  index regenerated coherently and is included without uncommitted audit
  references.
