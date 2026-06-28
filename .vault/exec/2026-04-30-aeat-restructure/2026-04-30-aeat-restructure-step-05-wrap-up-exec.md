---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-05-rebase-script-exec]]"
---

# 2026-04-30-aeat-restructure step-05 wrap-up

## status

Step 5 (Tooling prep) substantively complete after this PR lands. The `justfile` exposes the new tooling as named recipes for invocation by Step 5.5 (sandbox rehearsal), Step 7 (keystone), and Step 8 (acceptance gate).

Historical execution note: this record captures the pre-hard-cutover
tooling plan. The delivered rollout removed compatibility shims, and
`verify-shims` is not part of the active post-cutover contract.

## tooling matrix

| Artefact | PR | Recipe | Notes |
|---|---|---|---|
| import-linter contract | #488 | `just lint-imports` | Layered + independence + core-leaf-forbidden; carve-out registry of 9 per-file exceptions. Activates post-Step-7. |
| Shim-verification subroutine | #489 | `just verify-shims` | 4 modules / ~50 symbols. Step 8 semver-bump precondition. Exit 0 = all OK. |
| Mechanical rebase script | #490 | `uv run python scripts/rebase_imports.py [--reverse] [--apply]` | 39-entry rewrite map; `--reverse` for post-Step-9 rollback; 11-case test fixture. |
| Produce → verify → export smoke test | this PR | `just test-smoke-produce-verify-export` | Existing kent_e2e + kent_303_e2e tests are the load-bearing behavioural witnesses. Aliased through the justfile so Step 5.5 / Step 8 can invoke them as a unit. |
| Type-checker config | (deferred to Step 7) | `just typecheck` | Existing `[tool.ty]` config will be extended in Step 7 to scope the new layered subpackages. |
| Packaging verification | (deferred to Step 7) | (CI job) | A wheel-install + post-install layer-import smoke check rides in Step 7's keystone PR. |

## adr alignment

Per ADR Acceptance criteria, the 5 tooling-related criteria are addressed:

| ADR criterion | Tooling artefact |
|---|---|
| Static import-boundary enforcement (`import-linter` zero violations) | #488 contract |
| End-to-end behavioural smoke test | this PR justfile recipe + existing kent_e2e tests |
| Type-checker clean run | `[tool.ty]` (active today; scoping extended in Step 7) |
| Migration-script correctness test fixture | #490 11-case fixture |
| Packaging verification | deferred to Step 7 keystone PR |

The autonomous decision rule's preconditions (shim-verification gate; reverse rewrite map for rollback symmetry) are also in place.

## next step

Step 5.5 — sandbox dry-run rehearsal. Create a `restructure-dry-run` branch off main, run rebase script + import-linter + smoke test + reverse-map round-trip; verify all checks green; abandon the branch (Step 7 produces the canonical PR fresh).
