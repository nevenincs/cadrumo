---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-12'
modified: '2026-07-14'
body_hash: 'sha256:160984f38cc06e98ac7d597e4f030fe013d3af97f8df45642ae379dba309ddb8'
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

## Follow-on (2026-07-14): bounded Modelo-Wave family classified with real evidence

`2026-07-14-calculation-truth-registry-audit.md` classifies the 306-row
Modelo-Wave family (source lines 315-2604, Waves 0-27) using registry
directory presence, confirmed `src/aeat` package deletion, the Modelo 037
retirement decision, and cross-reference against the concurrently running
`calculation-export-import-adjudication` plan, replacing lexical matching with
real technical verification for that bounded family. `Tasks` (35),
`Teardown Replacement Contract` (359), and the `VAT Centralization Roll-Out
Ledger` (5) — 399 of 705 rows — remain unclassified and require the two
follow-up bounded adjudication passes the audit recommends. `P01.S01` still
does not cover all 705 rows and stays open.

## Closure (2026-07-14): all 705 rows classified

Per coordinator ruling, the remaining 399 rows were classified inside this
plan by two read-only verifier agents (Teardown Replacement Contract source
lines ~2605-4165 and ~3831-5064 plus Tasks), spot-checked and reconciled by
direct `find`/`rg` re-verification against `src/cadrumo` where the two
verifiers disagreed (Waves 6-8 export-directory presence for Modelo
190/193/347/369/840, the Modelo 036 censo reclassification, and the VAT
Centralization Roll-Out Ledger's 5 rows, independently verified — neither
verifier was assigned that section). The consolidated findings and full
705-row disposition table are recorded in
`2026-07-14-calculation-truth-registry-audit.md` (`teardown-tasks-vat-ledger-consolidated`,
`full-705-row-accounting`). Every unchecked legacy row now carries exactly one
of: delivered, superseded, blocked-external, blocked-derivative, inherited
from the completed `calculation-export-import-adjudication` plan (25/25 steps,
zero candidates passed its implementation gate), genuinely actionable, or
explicitly named unverified. `P01.S01` is complete: no row is silently
unaccounted for.
