---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:a9c758e6d7941018ae8c2dd34ca730ae4f9a570e867903dae67ca7d51b62fc0c'
step_id: 'S125'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Relocate the TUI pilot, replay, screenshot, surface registry, and fixture harness from the shipped product namespace to the development boundary, updating every consumer and deleting the product devtools package

## Scope

- `src/cadrumo/entrypoints/tui/devtools`

## Changes

- `D` the complete `src/cadrumo/entrypoints/tui/devtools` package, its README, and its colocated tests
- `A` `dev/tui/harness`, containing the relocated command, storage fixture, frame, journal, replay, surface registry, and Home/Modelo/profile/workbench fixture modules with their behavior tests
- `D` `dev/tests/test_public_devtool_homes.py`, the hand-maintained inventory of devtool modules, exports, edges, and expected file identities
- `M` `dev/tui/_harness.py`, `dev/tui/cli.py`, inventory tests, theme ownership, and documentation to invoke `dev.tui.harness` and enforce the one-way product boundary
- `M` `dev/audit/tests/test_unreachable_code.py` to exercise extra roots with an installed product module rather than a development command
- `M` product structural tests to remove the development replay exception and the development fixture from production censuses
- `M` `2026-08-11-tui-interface-adr` and `2026-08-11-tui-architecture-adr` through Vaultspec to withdraw the contradicted in-product harness placement
- `M` the reachability reference live module measurement from `50` to `32`
- `verify:` `python -m dev.tui.harness surfaces` -> full surface registry listed successfully
- `verify:` relocated harness, visual inventory, boundary, scanner, and affected product tests -> `141 passed`; two failures expose the separate peer-owned `src/cadrumo/entrypoints/tui/installed_session.py` event-loop site
- `verify:` focused repairs for product-boundary teeth and SVG identifier normalization -> `11 passed`
- `verify:` documentation parity and source parsing -> `9 passed, 1 skipped`
- `verify:` focused Python lint -> `all checks passed`
- `verify:` exact search -> no active code, development, recipe, or workflow reference to `cadrumo.entrypoints.tui.devtools` or `entrypoints/tui/devtools`
- `verify:` `just check-tui-render-coverage` -> expected red remains `8`, proving the same live surface registry is driven after relocation
- `verify:` `just check-unreachable-module-coverage` -> expected red reduced from `50` to `32`

## Notes

Development code now imports the product it evaluates in the ordinary one-way direction.
No product module imports, discovers, cites, or registers the harness. The moved harness
is absent from package discovery and installed command surfaces. The product event-loop
gate now tolerates tracked files deleted in the working tree; that correction revealed
the unrelated `installed_session.py` site instead of masking it behind a stale path read,
and this Step does not absorb or allowlist that peer-owned finding.
