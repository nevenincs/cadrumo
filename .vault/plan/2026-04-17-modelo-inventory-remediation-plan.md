---
tags:
  - '#plan'
  - '#modelo-inventory'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-17-modelo-inventory-remediation-adr]]'
  - '[[2026-04-17-modelo-inventory-remediation-research]]'
  - '[[2026-04-13-modelo-inventory-plan]]'
---

# `modelo-inventory` `remediation` plan

Correct the issue-108 modelo inventory and deadline/runtime surfaces so the
implemented behaviour matches the official AEAT/BOE rules validated in the
remediation research pass.

## Proposed Changes

The work will update both the static inventory and the runtime filing
projection so the project stops overstating completeness.

The remediation will cover:

- `037` historical/current-state correction.
- `193` addition and `123` annual linkage.
- `130` professional 70-percent withholding exception.
- `347` threshold-driven runtime support.
- CLI and runtime profile parity for employee, professional, rental,
  intracommunity, foreign-assets, and `347` threshold cases.
- Test invariants rewritten around behaviour instead of registry size.
- Fresh exec and audit artifacts replacing the earlier assumption that
  issue 108 was completely green.

## Tasks

- `Phase 1 - inventory and runtime model correction`
  1. Add `MODELO_193` and create `modelo_193`.
  1. Update `modelo_123` to point at `193`.
  1. Revise `modelo_037` and any tests or metadata that still treat it as
     the active current default.
  1. Extend `AutonomoProfile` with explicit flags for professional
     retenciones, the professional `130` exception, and the `347`
     threshold.

- `Phase 2 - deadline engine and CLI parity`
  1. Implement `347` in `aeat.domain.deadlines._calendar` and `_applies`.
  1. Refactor `111`, `190`, and `130` applicability to use the richer
     runtime profile.
  1. Update `aeat modelos year-plan` flags and profile projection logic to
     expose the new cases directly.

- `Phase 3 - tests and verification`
  1. Replace count-based enum and registry assertions with corrected
     behavioural tests.
  1. Add unit tests for:
     `037` historical/current treatment,
     `123 -> 193`,
     `347` threshold-driven inclusion,
     `130` suppression when the professional 70-percent exception applies,
     and CLI emission for the new runtime flags.
  1. Run the local quality gates and targeted CLI checks.

- `Phase 4 - vault traceability and final audit`
  1. Write exec step record(s) for the remediation.
  1. Persist a fresh audit document with triaged findings and closure.
  1. Write a remediation phase summary.

## Parallelization

Most code changes touch overlapping runtime and test surfaces, so
execution should stay mostly serial. Research and drafting already ran in
parallel, but implementation should proceed in one integrated pass to
avoid registry/runtime drift.

## Verification

Mission success requires all of the following:

- `just lint` passes.
- `just typecheck` passes.
- `just test` passes without adding mocks, patches, skips, or xfails.
- `uv run aeat modelos show 193 --json` succeeds.
- `uv run aeat modelos year-plan 2026 ... --json` can include `347` when
  the threshold flag is set.
- `uv run aeat modelos year-plan 2026 ... --json` suppresses `130` for the
  professional 70-percent exception case.
- The fresh audit contains no unresolved high-severity correctness
  findings for the remediated scope.
