---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-12'
modified: '2026-07-14'
step_id: 'S01'
related:
  - "[[2026-07-12-calculation-truth-registry-plan]]"
  - '[[2026-07-12-calculation-truth-registry-reference]]'
---

# Classify each legacy unchecked item against current source, accepted decisions, and recorded execution evidence

> **Review correction (2026-07-14): not complete.** This record preserves the
> mechanical 58/647 partition produced on 2026-07-12. It does not satisfy the
> Step title's row-by-row current-source and execution-or-decision evidence
> requirement. The governing plan has reopened `P01.S01`; the reference is an
> input index, not a final disposition ledger.

## Scope

- `.vault/plan/`
- `.vault/exec/`
- `.vault/audit/`
- `.vault/research/`

## Description

- Ground the current calculation authority with `vaultspec-rag` and read the
  complete continuation plan, accepted central-registry ADR, inventory
  research, current tracking audit, and legacy rebuild plan.
- Confirm that the legacy plan contains 705 `- [ ]` rows and zero canonical
  `Wxx.Pxx.Sxx` step rows, so the Vault parser's `0/0` is not progress data.
- Inspect the live registry and read-only filed-declaration capture boundaries
  in `src/aeat/domain/calculations/registry/`,
  `src/aeat/application/live/_filed_data_capture.py`, and
  `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- Create `2026-07-12-calculation-truth-registry-reference.md` as the
  deterministic source-line disposition index; retain all legacy checkboxes
  unchanged.

## Outcome

The reference mechanically accounts for every unchecked legacy row exactly
once:

- delivered: `0`;
- superseded: `0`;
- evidence-gated by the complete-bullet live/filed expression: `58`;
- unverified residual requiring current grounding: `647`.

The evidence-gated list is explicit and the unverified-residual set is its
complement over the hash-pinned 705-row source plan. This count was corrected
after review found that the first implementation inspected only the opening
physical line rather than the complete logical Markdown bullet. No code,
tests, user documentation, locales, or legacy plan state changed.

## Notes

The live-capture implementation is present and guarded, but it cannot create
the authenticated taxpayer evidence a matching row may require. The 58-row
evidence-gated set is a full-bullet lexical result, not a per-row external
blocker adjudication; the remaining 647 rows are mechanically classified as
unverified residuals, not individually proven actionable or delivered. This
historical run did not complete `P01.S01`. `P01.S02` and `P02.S03` remain
out of scope for this execution record.
