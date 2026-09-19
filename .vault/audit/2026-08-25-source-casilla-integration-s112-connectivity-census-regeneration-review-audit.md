---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8090f26700ec3d2752a381e3f095e0553549f933d655892293f73eb74ef8cf36'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S112 connectivity census regeneration review`

## Scope

Independent review of `2cb1324463`, including its repaired S112 execution
frontmatter, the canonical source-connectivity generator and selector archive,
the census, and S113/S115 handoff.  The review also checks whether the
concurrent TUI relocation affects structural discovery evidence.

## Findings

### generator-and-selector-drift | pass | live regeneration matches the recorded bounded drift

Direct generator execution finds 476 stable capability identities.  The frozen
`remaining_calculation_helpers` selector is 265 at digest
`sha256:3ddcba1760dbb46f65c8a1edd558516c24edb093348516bc01f1da73969aaddb`;
the live helper remainder is 267 at
`sha256:3b827ccf9f7fd2c3b30a37f042e9ede32be236d0b4600c8e3a09dcebbfeeeb6a`.
The two live additions are exactly
`calculation_helper:src/cadrumo/domain/calculations/registry/_temporal.py:revision_selection_coordinates`
and
`calculation_helper:src/cadrumo/domain/portals/_errors.py:portal_integrity_error`.
The selector gate refuses the stale digest rather than silently rewriting it.

### census-integrity-and-handoff | pass | census was not mutated or reclassified

`2cb1324463` has no census diff.  Current load confirms 15 entries, 17 explicit
capability claims, and five selectors.  The only entry expiry is 2026-12-31;
the governed follow-up deadlines are 2026-10-31 and 2026-11-30, so no row is
expired as of 2026-08-25.  The execution record accurately keeps both helper
identities unadjudicated and routes research to S113 and disposition to S115;
it neither changes their digest nor invents a census state.

### tui-relocation | pass | external temporary deletion does not invalidate structural evidence

The S112 generator is syntax-driven over production files and does not load
registry authority.  The contemporaneous TUI relocation's replacement is
committed at current head, and the same 476-identity result reproduces after
that repair.  It therefore does not undermine the generator or the archive
comparison; it only explained why a broader live-authority command was not
suitable at S112 execution time.

### execution-record-integrity | pass | repaired frontmatter and step status are coherent

The repaired execution record has valid schema/frontmatter and a truthful
scope: no census authoring occurred.  It distinguishes structural discovery
from authority, ownership, destination, lifecycle, and disposition decisions,
which remain with the named downstream steps.

## Recommendations

PASS.  Keep the helper selector's frozen digest unchanged until S113 grounds
both additions and S115 records their governed disposition.  Do not treat the
structural discovery result as a canonical source, binding, resolver, or census
promotion.
