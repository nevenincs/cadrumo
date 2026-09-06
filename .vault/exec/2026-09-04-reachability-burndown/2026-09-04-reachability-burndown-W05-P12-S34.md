---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:26a7a9252b0de71dc38ef52e3a94a6f3889bb6aedbc3c51d0618b2dd62a75279'
step_id: 'S34'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Repair the classification ledger's own drift, which had gone red on two gates: three clusters filed a symbol under an area the audit never names, so the staleness check read a live finding as one the audit had stopped reporting; the three PublicResultV1 models had genuinely stopped being reported because the dead projectors beside them construct them and a construction counts as a use even when the constructor is unreached; and the reported module import_preparation carried no entry at all, which the ledger requires and the earlier reading had wrongly ruled out; also adjudicate the process-cache reset seams as test-support after checking their docstrings' production claims against the closed override_settings field list

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py -m ""` -> `pass`
