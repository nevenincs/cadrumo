---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:138aa28cebf7b9ed356bba93781b2d2d1fc15ab419aaee24638e88afa51dc494'
step_id: 'S56'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
## Scope

- `src/cadrumo/entrypoints/tui/flows`
- `src/cadrumo/adapters/inbound/tui/__init__.py`

## Description

- Move the existing Textual flow app, question/review, confirmation, and selector projections to direct canonical modules.
- Rewire direct CLI, development-harness, and parity-test consumers without changing engine or wizard calls.
- Keep the canonical namespace facade inert and add concise public-method documentation required by the canonical production lint surface.
- Correct the review finding by deleting all moved Flow, Form, Confirm, and selector imports and exports from the legacy facade while retaining only the pending S104 Modelo view.

## Outcome

- Independently approved and complete; the S56 plan checkbox is closed.
- Commits: `59f33321d5` relocates the canonical flow renderer and direct consumers; `a030e9a941` removes the stale legacy facade exports.
- AST comparison proves each moved renderer is identical to its legacy implementation except direct relative-import names and documentation.
- Focused gates passed: scoped Ruff; ty for canonical flows and both Modelo wizard CLI consumers; the six-case Textual flow scroll-owner visual test; corrective facade import smoke; exact legacy definition/export census; and diff checks.

## Notes

- The three focused Textual flow failures are external contract drift, not S56 behavior: the two named submit-parity nodes leave `final_state` unset and the locale rebuild test retains `es-copy` after the English rebuild. The renderer control-flow AST is otherwise identical.
- `dev/tui/_surfaces.py` has seven pre-existing bare-generic `App` ty diagnostics; it remains outside the S56 ty result.
- The full migration/global census is integration-owned and was not refreshed during this path-scoped S56 closure.
