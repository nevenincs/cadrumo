---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:f4efb32e416f48879a41b07e0d9ab6fd9dcc4e753d14064a4802d09e392b35c8'
step_id: 'S356'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Let a caller spend the cursor the facet mints, or stop minting it. Verified: both public read entry points -- resolve_static_inspection_result and resolve_graded_snapshot_result -- accept page_size and NO cursor parameter, so a facet returns a valid next_cursor that no caller can redeem. RE-RESOLVING IS NOT A WORKAROUND AND MUST NOT BE PROPOSED AS ONE: a fresh capture invalidates the held cursor by construction, which is precisely the property the cursor exists to certify. The gap is load-bearing rather than cosmetic because paging is the normal case on the provenance destination, where the facet fans one source ref out per casilla it names

## Scope

- `src/cadrumo/application/modelo/workspace.py`
- `the two public resolver entry points`

## Changes

- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `verify:` `pytest test_workspace.py -k cursor` -> `5 passed (3 existing + 2 new)`
- `verify:` `ruff check workspace.py` -> `equals the HEAD baseline`

## Notes

Resolved by letting the caller spend the cursor, not by ceasing to mint it.
`paginate_modelo_workspace_facet` already validated and consumed a cursor in
full; the only gap was that neither public read entry point accepted one, so a
facet minted a `next_cursor` nothing could redeem.

Both resolvers now take `cursor: ModeloWorkspaceCursorV1 | None = None`. A
result assembles several facets from one call while a caller holds at most one
cursor, so `_facet_cursor` routes it by the facet the cursor itself names and
leaves the others at their first page -- applying one facet's offset to
another's records would be a silently wrong page.

A cursor naming a facet the resolver does NOT paginate refuses rather than
being ignored. Ignoring it returns page one while the caller believes it is
continuing, which is the exact failure the cursor exists to prevent.
`WORK_REVIEW` is deliberately outside `_GRADED_SNAPSHOT_PAGINATED_FACETS`: it
is assembled as its own facet type and never routed through the shared
paginator, so a cursor naming it can never be redeemed.

The new paging test drives the SAME public entry point twice and spends page
one's cursor on the second call. It compares record identities rather than
counts, because a call that silently restarted would match on length and on
has_more, and only the contents separate "continued" from "started over".
Re-resolving is not treated as a workaround anywhere: a fresh capture
invalidates a held cursor by construction, which is the property the cursor
certifies.

The resolver docstring promising that "a caller working through a larger
schema paginates via next_cursor" was false when written and is now true.
