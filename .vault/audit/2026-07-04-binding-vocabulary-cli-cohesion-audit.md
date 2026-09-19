---
tags:
  - '#audit'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-08-26'
body_hash: 'sha256:a0c2e0862844a542eebbb5b11dcdbf6f12ad7848da83a7cc02170bd3e39ae035'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# `binding-vocabulary-cli-cohesion` audit: `S23/S24 evidence review`

## Scope

Review of the S23 and S24 evidence records for the binding vocabulary CLI cohesion plan. The pass checked whether the records accurately reflect the current `work calculate` operator surface, whether they overclaim plan closure, and whether the reported verification failures are scoped to unrelated gate health rather than the W04.P07 binding vocabulary command paths.

## Findings

### s23-evidence-record | low | record is accurate and does not overclaim closure

The S23 record correctly states that the live CLI remains `aeat app modelo work calculate`, with envelope command and text operation `modelo.work.calculate`. That name is already the value-bearing calculation verb, so there is no stale `preview` or Sheets-pull wording to rename in this step. The record also correctly kept the plan checkbox untouched during the evidence pass and recorded the documented-command conformance failures as unrelated `aeat app agent` citations rather than S23 regressions.

### s23-gate-residual | low | documented-command conformance is now green after follow-up

The S23 evidence is enough to avoid redoing the operator-surface rename work. Follow-up commit `d2dad2d789` reconciled the unrelated `aeat app agent` citations in `README.md` and `docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md`, and `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` now reports `58 passed`.

### s24-blocker-record | low | verification blockers are recorded without claiming closure

The S24 record correctly separates green binding-vocabulary evidence from non-D9 blockers. JSON schema conformance is green, help-language parity and help-honesty are green under the integration marker, documented-command conformance is green, and source-only stale-command searches do not show stale `bindings preview` or `modelo.bindings.preview` command identifiers. Full `uv run --no-sync pytest --collect-only -q` is red again in the current shared worktree (`12182/14891 tests collected`, `2709 deselected`, `8 errors`) because non-authored untracked Modelo 145 registry scaffolding has no casilla files and no official workbook parity coverage. Locale audit is also red now: all four root catalogues are missing `cli.app.modelo.support_matrix.help`, introduced by non-authored support-matrix CLI WIP; the same locale files carry other non-authored additions. This audit still does not check the plan row or claim W04.P07 closure.

## Recommendations

- Keep S24 as an evidence/blocker record until collect-only and locale-gate evidence can be rerun without depending on non-authored WIP, then run `vaultspec-core vault plan step check` only for rows whose blockers have been resolved or formally accepted.
- Do not rename `work calculate`; it is already the canonical calculation verb and renaming it would broaden the operator-facing blast radius without satisfying a current mismatch.
- Treat the unrelated `aeat app agent` documented-command failures as resolved by `d2dad2d789`.
- Leave the locale-gate, support-matrix CLI WIP, and Modelo 145 registry WIP ownership issues to their owning tracks unless the coordinator moves those files into D9 scope.
