---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S04'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Add only the exact core state-root test helper route to the reporting contract

## Scope

- `.importlinter`

## Description

- Search the code semantic index for the core isolation, state-root, real secure-SQL helper, and reporting-contract route.
- Confirm the direct `cadrumo.core.tests.test_isolation_fixture_state_root_coverage -> cadrumo.tests.secure_sql` import and the helper's real persistence-storage adapter imports with targeted source and caller searches.
- Confirm the `core-not-outer` forbidden hierarchy, the existing test-to-adapter carveouts in both architecture contracts, and the existing `cadrumo.tests.secure_sql -> cadrumo.adapters.**` helper edge in the layered contract.
- Add only the exact core-test-to-helper route to the `core-not-outer` reporting contract; leave the layered contract and every production-core waiver unchanged.
- Exercise the core state-root isolation test through the real file-backed storage fixture and run the complete import graph in a fresh uncached process.

## Outcome

- The semantic search surfaced the architecture-reporting implementation; exact source tracing established that the core test imports the shared `isolated_cli_backend` fixture and that loading the helper reaches genuine storage adapters.
- The route is test-only: its importer is the structural core integration test, and the fixture exists to validate real state-root relocation. Production core has no import of this helper. Because `cadrumo.tests` is a cross-cutting support package outside the layer hierarchy, the direct helper edge is the only honest reporting exemption; widening a production-core waiver or ignoring a transitive adapter target would conceal a different dependency.
- `uv run --no-sync pytest -q -n0 -m integration` on the isolation coverage module passed `2` tests in `1.83s` against the real isolated storage fixture.
- `uv run --no-sync lint-imports --no-cache` analyzed `3421` files and `16152` dependencies. All five contracts were kept, zero were broken, and strict unmatched-ignore alerting remained satisfied.

## Notes

- The first focused pytest invocation inherited the repository's unit-only default marker and collected no tests. The explicit integration lane with xdist disabled then executed both intended real-storage tests successfully.
- No production waiver, layered-contract entry, test implementation, or helper implementation changed.
