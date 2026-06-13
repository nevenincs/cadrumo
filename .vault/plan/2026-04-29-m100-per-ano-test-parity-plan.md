---
tags:
  - '#plan'
  - '#m100-per-ano-test-parity'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-29-m100-per-ano-test-parity-adr]]"
  - "[[2026-04-29-m100-per-ano-test-parity-research]]"
---

# `m100-per-ano-test-parity` implementation plan

Add year-scoped parity tests for the seven non-B1 M100 anexos named in issue `#456`.

## Proposed Changes

- Add B2, C, D, E, F, G, and N test modules for 2024 and 2026.
- Preserve the 2025 worked-example structure, module markers, helper functions, and real `Engine` usage.
- Adjust Anexo G 2024 for the pre-Ley 7/2024 ahorro top-bracket value and keep 2026 aligned to the post-Ley 7/2024 surface.
- Record BOE source families and verification results in the execution and audit records.

## Tasks

- Inspect existing B1 year pattern and 2025-only target tests.
- Create 14 parity test files.
- Run focused parity tests and fix year-specific failures.
- Audit new tests for no mocks/skips and computed-casilla coverage.
- Run lint, typecheck, tests, hooks, and coverage.

## Parallelization

The anexo files are independent, but Anexo G requires serial year-specific review because it is the only file with a known 2024 versus 2025/2026 numerical delta.

## Verification

Focused pytest target: 126 new parity tests passed after splitting E and F. Computed-casilla audit found no missing 2024 or 2026 non-B1 computed casillas in the new files. Final verification should run `just lint`, `just typecheck`, `just test`, `just hooks`, and `just test-cov`.
