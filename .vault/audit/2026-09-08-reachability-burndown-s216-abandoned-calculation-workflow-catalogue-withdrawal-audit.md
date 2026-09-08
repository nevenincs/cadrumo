---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:550c584512c8015277435e44b009af671cadb8e61e87737ceb026ae561e3d61c'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S216]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

# `reachability-burndown` audit: `S216 abandoned calculation workflow catalogue withdrawal review`

## Scope

Independent review of W05.P12.S216, covering the alias removal in `application.modelo.calculation_route`, the resulting deletion of the unreachable core route enum, the already-unreachable operator-surface workflow catalogue and its tests, the relevant package-documentation cleanup, the focused calculation-route tests, the cadence materiality rule, and the S216 Step Record.

The review treated unrelated concurrent documentation cleanup in `application.operator_surface.__init__` as peer-owned and did not attribute it to S216.

## Findings

No critical, high, medium, or low findings.

The graph contraction is coherent. `CALCULATION_ROUTE_ID` was only a test-consumed alias of `ModeloCalculationRouteId.MODELO_WORK_CALCULATION`. Removing it leaves the one-member core enum with no consumer other than the abandoned workflow catalogue; that catalogue itself was consumed only by its synthetic test module. Exact residue search finds none of the deleted alias, enum, catalogue types, builder, or module identity in `src` or `dev`, and no ADR requires those identities.

The removed catalogue did not execute calculation. It projected three hard-coded command identities and CLI paths from synthetic reconciliation rows, then tested its own schema, ordering, refusal, and export census. Those tests were self-referential to an unreachable production model and did not protect a live product boundary. Their deletion follows the cadence rule that detailed synthetic contracts are not material when no real product consumer owns them.

Live ownership remains intact. `CALCULATION_ROUTE_RESOLVER_OWNERSHIP`, `require_calculation_route_resolver`, and the staged pre/post-mesh resolution paths remain production-consumed from `application.modelo.calculation_route`. The real CLI command identities and calculation paths remain present independently of the deleted operator catalogue.

The Step Record accurately names all S216 files and reports the focused 32-test suite, Ruff, exact residue, and the exact reachability result of 62 unreachable modules, 310 unused symbols, 15 orphaned tests, and 2027 of 2090 shipped modules reachable. The count changes match deletion of one now-unreachable production module and its orphaned test module rather than an allowlist, baseline, or compatibility mechanism.

## Recommendations

Approve W05.P12.S216. Retain the real resolver and CLI behavioral gates as the owners of calculation behavior; do not replace the deleted catalogue with another production inventory or development-disposition list.
