---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:72c9f2237e922d1a13647d8ec755feb7cce215c5c4ced5e2227937221e8bba89'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
---
## Scope

Formal read-only review of exactly dev/docs/terminology/_rung2_evaluation.py, dev/docs/terminology/tests/test_rung2_evaluation.py, and docs/_static/cadrumo-docs.js. Fresh uvx vaultspec-rag search CLI queries were run against port 8766 for the accepted consolidation ADR, source contract/reference, current plan, P02.S07 and P02.S31 execution records, and the exact changed seams. The accepted ADR and source contract were read in full before reviewing the implementation. The evaluator change is attributed to the prior LUNA Extra High worker; the current LUNA worker changed only the JavaScript seam.

The review is limited to contract parity, fail-closed status/count invariants, deterministic UTF-8 ordering, the Pagefind result.id and data().url join, D8 band-first preservation, security/licence boundaries, and shared-worktree scope. Unrelated peer WIP was inspected only to establish ownership and was not treated as a finding. No product/source/test code, generated artifact, plan, deployment state, staging area, commit, or remote was changed.

## Findings

### contract-parity-and-invariants | low | PASS: evaluator status, row, and aggregate contracts fail closed

dev/docs/terminology/_rung2_evaluation.py:151-158 requires CANDIDATES to carry candidates and rejects candidates for every abstention status. Lines 352-385 require hit rows to have HIT reason and an expected/candidate intersection, reject contradictory miss rows, require candidates for TARGET_MISMATCH, and reject candidate ids for abstention reasons. Lines 410-425 derive case, hit, miss, and miss-rate values from the validated rows and require the exact partition arithmetic. The associated real-behaviour tests at dev/docs/terminology/tests/test_rung2_evaluation.py:94-135 and 202-278 cover abstention, membership/reason, and aggregate contradiction cases. The focused evaluator test command passed 10 tests; ruff and basedpyright also passed on the evaluator.

### deterministic-ordering | low | PASS: UTF-8 ordering and relevance precedence remain deterministic

dev/docs/terminology/_rung2_evaluation.py:897-949 preserves relevance precedence and uses the explicit UTF-8 record-id comparator as the final tie-break. The focused tests at dev/docs/terminology/tests/test_rung2_evaluation.py:137-198 cover both UTF-8 id fallback and relevance-before-id precedence. In docs/_static/cadrumo-docs.js, the existing UTF-8 comparator at line 384 remains used for manifest ordering at lines 888-889, semantic record-id ties at line 1189, and final display ties at line 1736. No nondeterministic iteration or locale-sensitive ordering was introduced.

### pagefind-join-and-destination | low | PASS: Pagefind identity and destination use the correct fields

docs/_static/cadrumo-docs.js:1552-1567 awaits result.data(), passes data.url to cardFromPagefind, and stores the raw Pagefind result.id as pagefindId. Lines 1603-1621 build the lexical relevance map by result.id and join it through pagefindId; the fallback is a numeric maximum rather than an accidental URL key. The Pagefind JavaScript API contract was checked against its primary documentation: each result exposes id and result.data() exposes metadata including url. node --check passed, and the corrected integration selection uv run --no-sync pytest -q -m integration dev/docs/tests/test_palette_ranking.py dev/docs/tests/test_search_page_inline_ladder.py dev/docs/tests/test_search_page_fulltext_class_ranking.py passed 4 tests.

### d8-band-first-preservation | low | PASS: existing D8 display bands and semantic precedence are preserved

docs/_static/cadrumo-docs.js:1489-1549 continues to consume the shipped display_class and assign the existing card/full-text band ranks. Lines 1723-1738 retain band-first ordering, direct identity precedence, semantic strength/relevance tie-breaks, UTF-8 record-id fallback, and Pagefind relevance fallback. The current diff changes only Pagefind metadata capture and the relevance join; it does not alter the D8 comparator or band definitions. The same 4-test integration gate passed, and git diff --check passed.

### security-licence-and-scope | low | PASS: source-only, fail-closed, and ownership boundaries hold

docs/_static/cadrumo-docs.js:239-246 keeps the source-only Rung-2 boundary and manifest-owned targets; lines 666-683 retain same-origin fetching; lines 863-900 validate manifest shape, duplicate ids, ordering, and hashes; line 1115 returns null on bundle failure; and lines 1756-1805 continue to render user-controlled fields through textContent and static DOM/SVG construction. The evaluator patch adds validation and does not add provider I/O, downloads, raw source shipping, or a new licence surface; the accepted ADR's MIT provider boundary is unchanged. The exact unstaged product/test/source diff contains only the three requested paths, as shown by git diff --name-only, while .vault/audit/2026-08-06-user-docs-search-consolidation-audit.md is the sole audit scaffold. No unrelated peer WIP was staged, modified, or reported.

## Recommendations

No actionable source or test finding is recorded for this three-file review. Keep P02.S07 open: its standing Rung-2 report remains above the ratified miss-rate ceiling, so this review does not convert evaluator or browser evidence into Rung-2 acceptance or browser enablement.

P02.S31 now has recorded real-browser evidence: a local full Pagefind build, a 32-query capture, and the corrected focused integration gates. It remains open because the build used the documented sequence-check bypass and the capture is diagnostic rather than an accepted, reproducible full-ladder measurement. P02.S32 remains open for the independently versioned RAG-grounded query/alias authority. Deployment and the remaining locale/live gates remain outside this review.
