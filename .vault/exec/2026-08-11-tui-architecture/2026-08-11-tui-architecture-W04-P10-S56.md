---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b66fb5cc86d2926232ccb7bd7737c939643fd5750d7be5dd59a0d489fb2e403f'
step_id: 'S56'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
## Scope

- `src/cadrumo/entrypoints/tui/flows`

## Description

- Move the existing Textual flow app, question/review, confirmation, and selector projections to direct canonical modules.
- Rewire direct CLI, development-harness, and parity-test consumers without changing engine or wizard calls.
- Keep the canonical namespace facade inert and preserve all concurrent form-relocation work outside the staged S56 hunks.
- Add concise public-method documentation required by the canonical production lint surface.

## Outcome

- Open for independent review; the plan checkbox remains unchecked.
- AST comparison proves each moved renderer is identical to its legacy implementation except direct relative-import names and documentation.
- Focused checks passed: scoped Ruff; ty for canonical flows and both Modelo wizard CLI consumers; the six-case Textual flow scroll-owner visual test.
- Focused failures are external flow-contract drift: the two named submit-parity nodes leave `final_state` unset, and locale rebuild retains `es-copy` after the English rebuild. No flow semantics were changed.

## Notes

- `dev/tui/_surfaces.py` has seven pre-existing bare-generic `App` ty diagnostics; it remains outside the S56 ty result.
- The shared working tree also carries concurrent form and legacy-deletion changes. They remain unstaged and are not part of this record or commit.
