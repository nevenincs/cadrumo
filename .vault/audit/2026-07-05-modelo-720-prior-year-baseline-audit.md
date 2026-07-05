---
tags:
  - '#audit'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
  - "[[2026-07-05-modelo-720-prior-year-baseline-adr]]"
---
## Scope

Audited the W02.P03 Modelo 720 taxonomy implementation against the W02 plan, the M720 taxonomy ADR, BOE-grounded class-code intent, and the touched source/test files.

Audited implementation files: `src/aeat/core/aggregation.py`, `src/aeat/core/_foreign_asset_obligation.py`, `src/aeat/core/__init__.py`, `src/aeat/application/aggregation/_foreign_assets.py`, `src/aeat/core/tests/test_foreign_asset_obligation.py`, and `src/aeat/application/aggregation/tests/test_foreign_assets.py`.

## Findings

### import-boundary | medium | cross-package private import regressed the production import-hygiene gate

The first review pass found `src/aeat/application/aggregation/_foreign_assets.py` importing the new Modelo 720 class-code map and obligation helpers directly from `aeat.core._foreign_asset_obligation`. The focused runtime tests passed, but the repository import-hygiene gate proved this was a new production Family-1 violation. Resolution: `src/aeat/core/__init__.py` now exposes the foreign-asset obligation primitives from their owning source module, and `_foreign_assets.py` imports them from `aeat.core`. The real source remains `core._foreign_asset_obligation`; the facade is required only to satisfy the enforced package boundary.

### vault-trace | low | plan relation omitted the taxonomy ADR that governs W02.P03

The implementation steps were checked in the plan while the plan frontmatter still related only to the older June 2026 baseline ADR/research. Resolution: the plan now carries a related edge to `2026-07-05-modelo-720-prior-year-baseline-adr`, so W02.P03 traces to the taxonomy decision record. The ADR status remains `proposed`; that is preserved rather than silently promoted without an explicit ADR-approval action.

## Recommendations

- Keep W03 row-carrier work separate from this taxonomy commit; the new untracked row-carrier ADR placeholder is not part of the W02.P03 source migration.
- Before promoting the full feature to done, resolve or explicitly approve the taxonomy ADR status according to the ADR workflow.
- Continue to run the import-hygiene gate when changing cross-package imports; the production Family-1 gate is hard-zero.
