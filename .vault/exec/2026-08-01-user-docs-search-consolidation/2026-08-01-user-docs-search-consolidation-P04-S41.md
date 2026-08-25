---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:04387460c654b6b05b94a0e898745f334703f05314a672696ea909d1e6e0bd14'
step_id: 'S41'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Reconcile what the apex root owes between the pre-upload validation and the post-publish index verification

## Scope

- `dev/deploy/docs_static_site.py`
- `dev/deploy/tests/`

## Description

- Settle the contradiction between two surfaces that disagreed about whether the apex owes a search bundle.
- Extend the shared pre-upload composition to cover the apex as a root in its own right.
- Decide the fate of the validator that described exactly this contract and had no caller.

## Outcome

**The contradiction resolved in favour of the apex owing its bundle, and the disagreement was in the prose, not the tree.** The entry validator's docstring claimed the sitemap, the 404 page and the Pagefind bundle had moved into the language roots and that asserting them at the apex would demand files that correctly moved. The published-index verification simultaneously treats the apex as a root, fetches its served entry and raises when the built file behind it is absent. Both cannot be right. The tree settles it: the apex is not merely a language selector. It is the English full-scope build, the API tree lives nowhere else, and it carries its own sitemap, 404 page and search bundle. The language roots carry their own copies as well, so neither surface is the other's substitute. The docstring was overstating a real change and is corrected.

**The gap was one of ORDERING, and it was real.** The post-publish verification runs after the sync and after the cache invalidation. An apex that could not satisfy the publish would therefore have written to the live destination first and failed second, which is the same defect class the dry-run row was opened to remove one level up.

**The uncalled validator was revived rather than deleted.** It already composed exactly the apex contract, artifacts plus canonically-rooted sitemap plus record-bearing index, under the apex's own label. Deleting it and re-expressing the same three calls inline would have been a rewrite of working code, so it is now called from the shared composition and is dead no longer. The pre-upload validation is consequently a strict superset of what the post-publish check demands of the apex.

Landed in `09eee674c1`. A gate deletes exactly the file the post-publish verification would have demanded and requires the dry run to refuse, so the ordering fix cannot silently regress. The test helper was refactored so a site root's artifact set is written once and parameterised by its own canonical URL, and the dry-run fixtures now materialise a complete tree including the apex, because a tree that omits it is not a built site and must not stand in for one.

## Notes

Raised by the 2026-08-13 split-closure honesty review rather than by the original plan. It is rowed and recorded rather than folded into the row that introduced the shared composition, because it turned on a decision about what the apex owes and not on a mechanical omission.

One consequence worth stating plainly: this makes a publish refuse EARLIER than before in a case where it previously refused later. Nothing that could publish successfully before is refused now, and the whole point is that the refusal happens while nothing has been written outward.

The full deploy test module runs green at 69 passed. No live publish, no AWS call and no outward action was performed, and none is possible from this row.
