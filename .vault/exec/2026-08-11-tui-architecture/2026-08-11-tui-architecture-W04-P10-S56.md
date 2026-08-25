---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:4422bc2e74314f4997c367a82ca8e1885fb85123d2284fccea41f1456fd2d252'
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

- Open for independent review; the plan checkbox remains unchecked.
- AST comparison proves each moved renderer is identical to its legacy implementation except direct relative-import names and documentation.
- Focused checks passed: scoped Ruff; ty for canonical flows and both Modelo wizard CLI consumers; the six-case Textual flow scroll-owner visual test.
- The corrective facade import smoke, exact legacy definition/export census, Ruff, and diff check pass.
- Focused failures are external flow-contract drift: the two named submit-parity nodes leave `final_state` unset, and locale rebuild retains `es-copy` after the English rebuild. No flow semantics were changed.

## Notes

- `dev/tui/_surfaces.py` has seven pre-existing bare-generic `App` ty diagnostics; it remains outside the S56 ty result.
- Concurrent component-form changes remain unstaged; this corrective commit owns only the authoritative legacy facade removal required by no-reexport.
