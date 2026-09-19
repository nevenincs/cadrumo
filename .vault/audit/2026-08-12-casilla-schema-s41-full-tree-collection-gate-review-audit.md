---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:564fd7273fcd058c5337fdf6cf4d80aee99ec2403a2e2e425bc10c219f10a33b'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-11-casilla-schema-s01-import-and-collection-readiness-audit]]"
---
# `casilla-schema` audit: `W05.P11.S41 full-tree collection gate review`

## Scope

Formal read-only review of the S41 standing collection-gate correction and its execution record. The review compared each plan body with its previous blob, inspected project pytest configuration, grounded the command against the S01 audit, executed the final exact command, enumerated Git-tracked test roots, and checked VaultSpec ownership and document hygiene.

## Findings

### full-tree-testpaths | high | The first claimed full-tree command collected only configured testpaths

The first command, `uv run --no-sync pytest --collect-only -q -n 0 --override-ini=addopts=`, correctly cleared the default unit-marker selection and disabled xdist, but supplied no positional collection root. Pytest therefore continued to honor `tool.pytest.ini_options.testpaths`, which names only `src/cadrumo` and `dev/packaging/tests/test_installed_oracles.py`. It collected 29,087 tests across all marker cohorts in that configured suite, not the full tracked repository suite.

## Recommendations

Resolved. The plan now names `uv run --no-sync pytest src dev packaging --collect-only -q -n 0 --override-ini=addopts=` and accurately calls it the full tracked-suite serial collection. Git's tracked-file census with `git ls-files '*test_*.py'` finds 2,849 files under `src`, 271 under `dev`, 4 under `packaging`, and no fourth root. The explicit roots cover every tracked matching test file while excluding untracked shared-worktree probe copies.

The execution record now distinguishes all three boundaries honestly. The no-root command's 29,087 count is reclassified as configured-`testpaths` evidence. The `.` probe is disclosed as contaminated by untracked shared-worktree copies and its 2,090 collection errors are not described as product failures. The final three-root command is the retained reproducible gate.

## Resolution

The high-severity finding is **resolved**. The final exact tracked-root command independently exited zero with 32,280 tests collected in 74.78 seconds, corroborating the execution record's 32,280 in 71.62 seconds. Clearing `addopts` remains load-bearing because the project default selects only `unit and not external_tool and not os_keychain`; explicit roots now independently close the `testpaths` omission.

The plan mutation remains surgically narrow: relative to the rejected intermediate command, only `tracked-suite` and the three positional roots were added, plus the CLI-maintained body hash. No checklist state, step wording, unrelated verification rule, or prose block changed. The plan and execution record have current VaultSpec body hashes and modified stamps; Markdown, diff, encoding, links, and structural checks are clean. The remaining feature-index, S02 body-section, and S34 modified-stamp warnings are unrelated to S41.

Final verdict: **PASS**. S41 now defines and proves a repeatable full tracked-suite collection gate without claiming untracked workspace probes as repository tests. No S41 finding remains open.
