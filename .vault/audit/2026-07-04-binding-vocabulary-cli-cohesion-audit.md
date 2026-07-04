---
tags:
  - '#audit'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-W04-P07-S23]]"
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-W04-P07-S24]]"
---

# `binding-vocabulary-cli-cohesion` audit: `S23/S24 evidence review`

## Scope

Review of the S23 and S24 evidence records for the binding vocabulary CLI cohesion plan. The pass checked whether the records accurately reflect the current `work calculate` operator surface, whether they overclaim plan closure, and whether the reported verification failures are scoped to unrelated gate health rather than the W04.P07 binding vocabulary command paths.

## Findings

### s23-evidence-record | low | record is accurate and does not overclaim closure

The S23 record correctly states that the live CLI remains `aeat app modelo work calculate`, with envelope command and text operation `modelo.work.calculate`. That name is already the value-bearing calculation verb, so there is no stale `preview` or Sheets-pull wording to rename in this step. The record also correctly keeps the plan checkbox untouched because the plan file has non-authored WIP, and it records the documented-command conformance failures as unrelated `aeat app agent` citations rather than S23 regressions.

### s23-gate-residual | low | documented-command conformance remains red outside S23

The S23 evidence is enough to avoid redoing the operator-surface rename work, but the broader documented-command conformance gate is still red because of unrelated `aeat app agent` citations in docs. This audit does not treat that as an S23 blocker, but the campaign cannot honestly claim a globally green documented-command gate until that separate docs surface is reconciled by its owner.

### s24-blocker-record | low | verification blockers are recorded without claiming closure

The S24 record correctly separates green binding-vocabulary evidence from non-D9 blockers. JSON schema conformance is green, help-language parity and help-honesty are green under the integration marker, and source-only stale-command searches do not show stale `bindings preview` or `modelo.bindings.preview` command identifiers. The record also names the real blockers: full collect-only cannot complete in this Windows environment without `pywintypes`; the root locale audit is red on corpus-bundle signing keys introduced by concurrent work; and documented-command conformance is red on unrelated `aeat app agent` docs citations. It does not check the plan row or claim W04.P07 closure.

## Recommendations

- Keep S23 and S24 as evidence/blocker records until the shared plan WIP clears, then run `vaultspec-core vault plan step check` only for rows whose blockers have been resolved or formally accepted.
- Do not rename `work calculate`; it is already the canonical calculation verb and renaming it would broaden the operator-facing blast radius without satisfying a current mismatch.
- Leave the unrelated `aeat app agent` documented-command failures to the owning docs/harness track rather than folding them into the bindings vocabulary step.
- Leave the corpus-bundle signing locale keys and `pywintypes` collection issue to their owning tracks unless the coordinator moves those blockers into D9 scope.
