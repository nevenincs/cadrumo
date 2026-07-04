---
tags:
  - '#audit'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-W04-P07-S23]]"
---

# `binding-vocabulary-cli-cohesion` audit: `S23 evidence review`

## Scope

Review of the S23 evidence record for the binding vocabulary CLI cohesion plan. The pass checked whether the record accurately reflects the current `work calculate` operator surface, whether it overclaims plan closure, and whether the reported verification failures are scoped to unrelated documentation citations rather than the S23 command path.

## Findings

### s23-evidence-record | low | record is accurate and does not overclaim closure

The S23 record correctly states that the live CLI remains `aeat app modelo work calculate`, with envelope command and text operation `modelo.work.calculate`. That name is already the value-bearing calculation verb, so there is no stale `preview` or Sheets-pull wording to rename in this step. The record also correctly keeps the plan checkbox untouched because the plan file has non-authored WIP, and it records the documented-command conformance failures as unrelated `aeat app agent` citations rather than S23 regressions.

### s23-gate-residual | low | documented-command conformance remains red outside S23

The S23 evidence is enough to avoid redoing the operator-surface rename work, but the broader documented-command conformance gate is still red because of unrelated `aeat app agent` citations in docs. This audit does not treat that as an S23 blocker, but the campaign cannot honestly claim a globally green documented-command gate until that separate docs surface is reconciled by its owner.

## Recommendations

- Keep S23 as an evidence/reconciliation record until the shared plan WIP clears, then run `vaultspec-core vault plan step check` for `W04.P07.S23` only if the coordinator accepts evidence-only closure for the already-aligned `work calculate` surface.
- Do not rename `work calculate`; it is already the canonical calculation verb and renaming it would broaden the operator-facing blast radius without satisfying a current mismatch.
- Leave the unrelated `aeat app agent` documented-command failures to the owning docs/harness track rather than folding them into the bindings vocabulary step.
