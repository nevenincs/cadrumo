---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:11a3b4bb893c435945d1d3ca238bf0889e6ac58aac93e4e46fe312982ad0b586'
step_id: 'S46'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Run the feature-surface gate over the touched storage, transaction, aggregation, and modelo paths

## Scope

- `src/aeat`

## Description
- Scope the feature-owned Python surface to 22 files under persistence profile/storage,
  aggregation/modelo source mesh, and transaction models/tests.
- Run ruff on the scoped Python files with `uv run --no-sync ruff check`.
- Run pytest on the scoped feature-owned test modules with `uv run --no-sync pytest -q -n 0 -x`.
- Run feature-scoped vault hygiene checks, repair local documentation hygiene, and add
  the missing research relation to the accepted read-path ADR.
- Rebuild the `ledger-latency-budget` feature index and rerun the feature-scoped vault
  check.

## Outcome
- `uv run --no-sync ruff check` passed on all 22 scoped Python files.
- `uv run --no-sync pytest -q -n 0 -x` passed on the 12 scoped test modules:
  184 passed, 6 integration benchmark cases deselected by the normal marker policy, in
  26.26s.
- `uv run --no-sync vaultspec-core vault check all --feature ledger-latency-budget`
  now reports clean feature-owned structure, frontmatter, modified stamps, annotations,
  markdown, links, dangling links, body links, placeholders, orphans, feature index,
  references, schema, ADR status, rename integrity, and encoding.
- The same vault command still exits nonzero because `feature-rename-integrity` reports
  29 pre-existing global exec-folder rename errors outside `ledger-latency-budget`.

## Notes
- The accepted read-path ADR now relates to the research baseline so the feature schema
  check is clean.
- The six deselected tests are the integration benchmark nodes already run explicitly
  during S39 and S40 for latency evidence.
- The remaining vault failure is not in this feature's authority: all named error paths
  are older exec folders such as `2026-04-17-modelo-inventory-remediation`,
  `2026-04-20-pdf-import`, and schema-hardening folders whose folder feature segment
  disagrees with their existing record tags.
