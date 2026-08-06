---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:9f914afb2a9f78fc4e144acfc460581063b41005c4d10d6e3691cc92cd6ec8fe'
step_id: 'S08'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Delete the search optional extra with its model2vec, huggingface-hub, and numpy pins, prune the all aggregate, promote snowballstemmer into the core dependency set, and refresh the lockfile

## Scope

- `pyproject.toml`

## Description

- Delete the `search` optional extra and its model2vec, huggingface-hub, and numpy pins from `pyproject.toml`; prune the `all` aggregate.
- Promote `snowballstemmer` into the core dependency set, since the stemmed FTS column is now the only shape the lexical index has.
- Refresh `uv.lock`.
- Drop the command index's now-unreachable `ModuleNotFoundError` fallback branch that silently fell back to unstemmed terms, since the stemmer is no longer optional.
- Update `THIRD_PARTY_NOTICES.md` to drop the potion/model2vec/C4 lineage section, since no model is loaded and no vectors are computed.
- Update `dev/packaging/smoke_core.py`'s optional-extra-registry assertion for the narrowed extra set.

## Outcome

Landed as commit `13935ef3a2` "build(search): drop the search extra and its dependency refusal". Confirmed by `git show --stat 13935ef3a2`: `pyproject.toml` changed 40 lines, `uv.lock` changed 33 lines, `THIRD_PARTY_NOTICES.md` dropped 32 lines (net), `command_search/_index.py` changed 16 lines to drop the stemmer fallback, `dev/packaging/smoke_core.py` changed 7 lines. `uv tree --no-dev` was run and confirmed none of model2vec, huggingface-hub, or numpy remain in the product closure; only model2vec actually left the lock, as huggingface-hub and numpy remain dev-group transitives of `vaultspec-rag`, the dev-side compilation oracle the ADR keeps.

## Notes

The plan's Verification section states "the lockfile resolves without the three retired packages"; that wording is inaccurate as literally read. Only model2vec left the lock outright. huggingface-hub and numpy correctly remain, as dev-group transitives of `vaultspec-rag` (the architecture's dev-side oracle, out of scope for retirement). The `uv tree --no-dev` check is the correct verification: it confirms none of the three are reachable from the product (non-dev) dependency closure. An architecture agent is separately amending the plan/ADR verification prose; this exec record does not edit that text per the coordinating brief's instruction, and only records the discrepancy for the closure trail.
