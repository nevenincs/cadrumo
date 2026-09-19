---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:cade6eca5c43d2acbcba0088f49fc486af13c34aa5014db9f83cb4b12af49612'
step_id: 'S33'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Propagate the nested query-alias authority provenance through the Rung-2 bundle and browser validator, rejecting the pre-amendment shape

## Scope

- `dev/docs/terminology/_rung2_bridge.py`
- `docs/_static/cadrumo-docs.js`
- `dev/docs/terminology/tests/`

## Description

Update the browser-side Rung-2 provenance validator to accept exactly the ADR Update 11 nested query-alias authority identity, validate its schema/version/path/digest, and reject the old flat-only payload. Preserve the typed Python bundle path and keep Rung-2 disabled until the existing acceptance evidence passes.

## Outcome

The Python bundle already serializes the required typed nested provenance through `Rung2InputProvenance`. The browser validator now requires `query_alias_authority` with the exact schema literal, positive authority version, repository-relative source path, and SHA-256 digest. Unknown nested or top-level fields remain fail-closed. No browser enablement, matrix, release, or deployment occurred.

## Verification

```
node --check docs/_static/cadrumo-docs.js
exit 0

uv run --no-sync pytest -q -m integration dev/docs/tests/test_search_page_fulltext_class_ranking.py
1 passed in 10.76s

uv run --no-sync pytest -q -m integration dev/docs/tests/test_palette_ranking.py dev/docs/tests/test_search_page_inline_ladder.py dev/docs/tests/test_search_page_fulltext_class_ranking.py
3 passed; 1 Windows Playwright TargetClosedError during the full-text fixture teardown (not counted as green)

uv run --no-sync vaultspec-rag search "Rung2 alias authority fail closed raw byte provenance combined sweep inputs" --type code --port 8766 --timeout 120
completed successfully

uv run --no-sync vaultspec-rag search "Update 11 independent query alias authority provenance exact parity held out" --type vault --doc-type adr --port 8766 --timeout 120
completed successfully
```

## Notes

- The review finding was grounded against the accepted Update 11 ADR and the current browser validator; the browser was still enforcing the pre-amendment flat provenance shape.
- The rerun of the failed full-text browser case passed in isolation. The multi-test run remains recorded as a partial/unverified boundary rather than being waved through.
- Deployment remains deferred and Rung-2 acceptance remains open.

### 2026-08-06 follow-up review hardening

The adjacent P02.S32 provenance review also added a raw-byte/model identity tamper guard; the complete Rung-2 suite remains `62 passed in 8.67s`. The browser correction itself remains source-only and Rung-2 stays disabled.
