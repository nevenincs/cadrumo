---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:f3fbc30c8e7282c9d62649ac8196e8bb3145cb72cfa7b7297daa68fbc41f2396'
step_id: 'S290'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Give the byte-identical FTS or-group builder one shared leaf home, since both copies sit in application packages that may not reach into each other

## Scope

- `src/cadrumo/application/command_search/_index.py`
- `src/cadrumo/application/corpus_search/_lexical_index.py`

## Description

- Confirmed the private `_fts_or_group` in `command_search/_index.py` and `corpus_search/_lexical_index.py` were byte-identical: a term stripper, first-seen de-dup, quote, and `" OR "` join for SQLite FTS5.
- Chose `core` as the shared leaf home. The layered contract order is `application > domain > core`, so `core` is a leaf every application package may legally import, and both packages already import from `core`. `core` avoids any application-to-application coupling and any cycle (`command_search` already imports `corpus_search`, so the shared home could not live in either search package without risking a cycle).
- Created `core/_fts_query.py` with a public `fts_or_group` and exported it through the `core` package facade (`core/__init__.py` import plus `__all__`).
- Deleted both private copies and routed all three call sites (`command_search` FTS key search; `corpus_search` folded/stemmed match expression) through `from ...core import fts_or_group`.
- Ran the tree-wide apidocs scaffold; it changed exactly the two stubs naming my new module (`docs/api/cadrumo.core._fts_query.rst` new, `docs/api/cadrumo.core.rst` toctree), no peer modules, and `scaffold --check` is conformant.

## Outcome

The FTS5 OR-group builder now has one owner, `fts_or_group` in the `core` package, consumed by both search indexes through the core public facade. Neither search package reaches into the other for this helper.

Home-selection rationale (per the layered contract): `command_search` and `corpus_search` are peer application packages; `core` is the innermost leaf both may import in the sanctioned inner-ward direction, and the builder is pure standard-library FTS5 query-string infrastructure with no domain or application knowledge, so it belongs there rather than in either peer.

Discovery basis: the mandated `vaultspec-rag` code index was measured untrustworthy (mid-rebuild, control probes missed), so a structural AST duplicate scan supplied the cluster and every claim was re-established by exact `rg` search and by reading both bodies and `.importlinter`.

Verification (HEAD `13fe2c9b8b29e8f6b08ea483e4a1390b713dea61`):

- `uv run --no-sync ruff check` / `ruff format --check` clean on all four touched source files.
- `uv run --no-sync python -m dev.docs.apidocs scaffold --check` — `Stub tree is conformant. No drift detected.`
- `uv run --no-sync pytest src/cadrumo/application/command_search/tests/test_command_index.py src/cadrumo/application/corpus_search/tests/test_lexical_index.py src/cadrumo/application/corpus_search/tests/test_retrieval.py -n0 -q` — 18 collected, `18 passed in 12.46s`.
- Mutation proof: perturbing the shared core `fts_or_group` (`" AND "` join with a `zzz` term suffix) reddened both packages simultaneously — `8 failed, 10 passed`, with 3 command_search and 4 corpus_search failures — proving both genuinely consume the single core function; restored to `18 passed`.

## Notes

None. The apidocs scaffold is tree-wide but produced only my module's two stub deltas; both are staged with this Step.
