---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S78'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Run focused runtime, persistence, CLI, MCP, agent, and packaging tests with real behavior

## Scope

- `Cadrumo feature test surface`

## Description

- Reconcile the canonical Cadrumo executable after quarantining an unapproved concurrent CLI detour.
- Repair the corrupted product-identity contract so it imports the public Cadrumo facade and asserts the accepted tuple.
- Run focused runtime, persistence, CLI, MCP, agent, companion-packaging, sealed-archive, and MCPB behavior tests without mocks, skips, or expected failures.
- Redirect artifact-build temporary storage and the uv cache to the workspace drive after the system drive exhausted its free space.
- Narrow the retired MCPB assertion to the actual artifact name so the repository parent path cannot create a false positive.

## Outcome

The focused Cadrumo feature surface is green. Ten identity, import-hard-cut, installed-console, root-help, documented-command, educational-document, and self-referential-command checks passed serially. A broader runtime matrix then passed thirty-five tests before artifact setup encountered shared temporary-directory exhaustion. Re-running the artifact slice with isolated workspace-local temporary and cache roots passed twenty-nine companion-wheel, shared-namespace, persistence archive, MCPB, and distribution-budget checks. The final evidence is sixty-four passing real-behavior tests with no product assertion failure.

## Notes

An earlier parallel run crashed an xdist worker, so the accepted evidence uses serial execution to remove worker instability from the product signal. The system drive had about sixteen megabytes free and could not stage companion wheels; the workspace drive had sufficient capacity and completed the same builds. No product source or evidence bytes were changed to accommodate the environment. Public publication remains outside this Step and blocked by the external reservation gate.

## Fresh HEAD-current pass (2026-07-15)

Re-ran the focused suites against current HEAD, isolating `CADRUMO_LOCAL_STORAGE_ROOT`
to a scratch directory so a stale local `var/aeat.db` could not trip the
`FormerProductStateError` refusal:

- `src/cadrumo/entrypoints/cli/tests`, `src/cadrumo/entrypoints/mcp/tests`,
  `src/cadrumo/agent/tests`, `src/cadrumo/core/identity/tests`,
  `src/cadrumo/core/access_gate/tests`,
  `src/cadrumo/adapters/persistence/storage/tests` (`-n auto`): 348 passed.
- `dev/packaging/tests` (`-n auto`): 15 passed.
- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
  and `test_cadrumo_state_identity_acceptance.py` (explicit re-run): 25 passed.
- `src/cadrumo/core/tests` (`-n auto`): 358 passed, 1 failed —
  `test_period_combined_string_gate.py::test_repo_has_no_unallowlisted_combined_period_strings`,
  failing on `docs/_sequences/how-to/{filing-calendar,troubleshooting,verification-reports}/*.json`
  fixtures. `git log -1` on those paths attributes the most recent change to
  commit `c8a78ab1d37` ("docs(docs-cli-sequences): convert filing-calendar
  residual fences to sequences and @static"), an unrelated concurrent campaign;
  no commit on the rename feature touches those fixture files. Recorded per
  `full-tree-gate-must-distinguish-owner` as owned by the `docs-cli-sequences`
  campaign, out of this feature's scope, and not fixed here.

Total: 746 tests run, 745 passed, 1 pre-existing failure on a peer-owned
surface. Step closed on this fresh-pass evidence in addition to the prior
64-test run recorded above.
