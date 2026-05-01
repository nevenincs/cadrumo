---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-05-rebase-script-exec]]"
---

# 2026-04-30-aeat-restructure step-05 wrap-up

## status

Step 5 (Tooling prep) substantively complete after this PR lands. The `justfile` exposes the new tooling as named recipes for invocation by Step 5.5 (sandbox rehearsal), Step 7 (keystone), and Step 8 (acceptance gate).

## tooling matrix

| Artefact | PR | Recipe | Notes |
|---|---|---|---|
| Historical import-linter contract | #488 | superseded | Replaced by pytest import-contract tests in the delivered hard-cutover. |
| Historical shim-verification subroutine | #489 | superseded | Replaced by canonical-path import-contract tests and deleted-root-module absence checks. |
| Mechanical rebase script | #490 | `uv run python scripts/rebase_imports.py [--reverse] [--apply]` | 39-entry rewrite map; `--reverse` for post-Step-9 rollback; 11-case test fixture. |
| Produce → verify → export smoke test | this PR | `just test-smoke-produce-verify-export` | Existing kent_e2e + kent_303_e2e tests are the load-bearing behavioural witnesses. Aliased through the justfile so Step 5.5 / Step 8 can invoke them as a unit. |
| Type-checker config | (deferred to Step 7) | `just typecheck` | Existing `[tool.ty]` config will be extended in Step 7 to scope the new layered subpackages. |
| Packaging verification | (deferred to Step 7) | (CI job) | A wheel-install + post-install layer-import smoke check rides in Step 7's keystone PR. |

## adr alignment

Per ADR Acceptance criteria, the 5 tooling-related criteria are addressed:

| ADR criterion | Tooling artefact |
|---|---|
| Static import-boundary enforcement (import-contract zero violations) | pytest import-contract tests |
| End-to-end behavioural smoke test | this PR justfile recipe + existing kent_e2e tests |
| Type-checker clean run | `[tool.ty]` (active today; scoping extended in Step 7) |
| Migration-script correctness test fixture | #490 11-case fixture |
| Packaging verification | deferred to Step 7 keystone PR |

The autonomous decision rule's accepted preconditions are canonical import-contract verification and the reverse rewrite map for rollback symmetry.

## next step

Step 5.5 — sandbox dry-run rehearsal. Create a `restructure-dry-run` branch off main, run rebase script + import-contract tests + smoke test + reverse-map round-trip; verify all checks green; abandon the branch (Step 7 produces the canonical PR fresh).
