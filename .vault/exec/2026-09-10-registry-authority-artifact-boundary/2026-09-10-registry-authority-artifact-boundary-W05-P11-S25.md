---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:4c9b0bbedaade57cb472dbc9b7bbe21a24cb1652df0592a22122acc3fdb4c6eb'
step_id: 'S25'
related:
  - '[[2026-09-10-registry-authority-artifact-boundary-plan]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-remediation-result-reference]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-authority-backend-final-review-audit]]'
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Measure fresh-process post-import load, peak memory, first snapshots, warm queries, and full enumeration; record results without asserting unapproved product budgets

## Scope

- `dev/registry/benchmark_authority.py`

## Changes

- `A` `dev/registry/benchmark_authority.py`
