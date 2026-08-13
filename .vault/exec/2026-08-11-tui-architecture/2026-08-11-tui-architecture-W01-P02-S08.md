---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9f63b85411c6727d6e8d6bc32a32560ae9a06da12ac7b3b473108c3799264b7a'
step_id: 'S08'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define validated per-operation capability declarations and forbidden capability combinations

## Scope

- `src/cadrumo/application/operations/_capabilities.py`
- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/application/operations/tests/test_capabilities.py`

## Description

- Ground capability vocabulary and invalid combinations in the accepted operation-platform ADR, its research evidence, the completed S06 lifecycle axes, and semantic code and vault discovery.
- Define one strict, frozen `OperationCapabilities` authority with explicit durability, cancellation, deadline, replay, baseline, sensitive-input, conflict-scope, resource, effect, and close-policy declarations.
- Refuse unsafe durability/replay, lease, effect, cancellation, deadline, resource-ownership, and close-policy combinations at model validation.
- Preserve canonical relative self-imports in colocated tests and add the missing operation-package ownership marker without exporting a premature public facade.
- Prove required declarations, strictness, immutability, forbidden combinations, valid configurations, and standard pytest package collection through direct real-model tests.

## Outcome

- Live code and vault semantic searches succeeded on port 8766. Whole-file reads and targeted `rg` confirmed `OperationCapabilities` as the single per-definition declaration authority; S06 core enums own generic axes, cleanup primitives own mechanics, and service, profile, registry, and frontend capability models govern distinct concepts.
- A second live semantic search for pytest package topology returned the accepted relative-import authority and collection gates. Reading `dev.quality.relative_imports`, the accepted ADR, topology review, pytest configuration, package markers, and layout/import tests showed the imports were canonical but their parent package marker was missing.
- Added only a docstring-only `application.operations` package marker. It exports no symbol and therefore does not pre-empt the S11 public-facade step.
- Ephemeral operations cannot conceal governed effects or promise durable replay, durable operations require lease scope, resumability is symmetric with replay, and stopping promises require truthful cancellation/resource support.
- Current focused verification passed: `uv run pytest src/cadrumo/application/operations/tests/test_models.py src/cadrumo/application/operations/tests/test_capabilities.py -q` reported `31 passed in 5.90s`; Ruff reported `All checks passed!`; basedpyright reported `0 errors, 0 warnings, 0 notes`; `uv run python -m dev.quality.relative_imports` over the four focused files exited zero.

## Notes

- Initial semantic queries were refused with `quiesce_admission_closed`; no final claim relies on that fallback. After sanctioned service recovery, required searches succeeded and their returned owners were adjudicated.
- The earlier code search warned that its index held `94389` of `96048` published sections, with `1659` missing. Absence was not treated as evidence; targeted repository-wide search supplied the duplicate and consumer census.
- Concurrent shared-worktree activity captured the production module and test in reachable commit `56972648206dd16e788ede009b655104cd427b6f` and an earlier exec version in reachable commit `4a0fff1926e904078720631d71ff411d5c958803`; history was not rewritten.
- The previously preserved relative-import WIP is now authorized and retained unchanged. The failure was package topology, not import syntax; `--import-mode=importlib` reproduced the same pre-fix collection error.
- Final independent review closed all critical, high, and medium findings. The binding plan row was closed through `vault plan step check`. `uvx vaultspec-core vault check all` exited zero with `1398 warnings`; current global residuals include 19 annotation warnings, 17 markdown warnings, 10 feature warnings, 29 schema warnings, 3 modified-stamp warnings, and the pre-existing body-schema corpus findings reported by the command.

