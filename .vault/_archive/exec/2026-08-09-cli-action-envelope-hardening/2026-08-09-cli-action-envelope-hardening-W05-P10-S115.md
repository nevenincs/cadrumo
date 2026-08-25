---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:bb0584e6027007f21080e986705279528a6a5d5af92c8060255b57e50d242a6c'
step_id: 'S115'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate the active-session diagnostics recovery producer to typed conditions and canonical action or explicit no-recovery outcome

## Scope

- `src/cadrumo/application/diagnostics.py`

## Description

- Replace the rendered-text scan in the missing-active-bucket-session classifier with a typed exception-chain walk.
- Follow both the cause and context edges instead of only one, and mark visited links so a cyclic chain terminates.
- Add regressions pinning the typed classification, the removal of the false-positive text match, and cycle termination.

## Outcome

- The active-session verdict is now derived entirely from the typed exception chain. It decides whether the secure-state row warns as an expected cold start or fails as a real fault, and whether the raw exception detail is withheld from the operator, so it is a classification with an operator-visible consequence rather than an internal convenience.
- The substantive finding is that the text scan could not have survived this campaign, and was already dead in the direction it was written for. The producer it looked for takes no authored sentence, so its rendered form is the locale key for the registered no-active-session refusal, which does not contain the class name. Any wrapper carrying that text forward therefore no longer mentions the class, and the scan would have quietly stopped matching, reporting every cold start as a hard fault and surfacing raw plumbing text the surrounding code deliberately withholds.
- The scan also matched in the wrong direction. Any unrelated failure whose message merely mentioned the class name was classified as an expected cold start, which downgrades a genuine fault to a warning and suppresses the detail the operator needs to act. The replacement refuses that case, and a regression pins it.
- The previous walk followed a single edge per link, taking the cause when present and the context otherwise, so it abandoned the context branch whenever a cause was set. A chain that forks across the two edges hid the typed link from the walk entirely, which is the realistic wrapped shape: an incidental re-raise inside an except block sets only the context edge while an explicit raise-from sets only the cause. The new walk follows both, so it is strictly stronger than the old typed path as well as free of the text scan.
- Following two edges makes a revisit possible, so the walk marks links by identity. The repair surface is what an operator reaches for when the application is already unhealthy, so a non-terminating classifier there would strand the one command meant to explain the failure. A regression builds a mutually referential chain and pins termination.
- Three regressions pass in the owning module and all thirty-five tests in it pass. The module is unit-marked, so these run in the default per-push lane rather than behind an integration marker.
- The regressions are proven to discriminate: restoring the pre-migration classifier out of repo fails the typed-chain assertion, returning false where the migrated code returns true. Nothing under the source tree was mutated to obtain that proof.
- Ruff check and format are clean on both changed files.

## Notes

- The box is deliberately left unchecked. This is a producer-migration row and a rehoming ledger owner, and checking it while the owning qualname still yields fingerprints adds to the owner-closed finding set already open against twelve closed Steps. The blocking analysis and the pending decision are recorded in the rehoming ledger owner-closed audit. The ledger writer was not run and no ledger entry was touched: this Step's single owned entry is a reference-role site whose surrounding expression is unchanged by the migration.
- Deliberately out of scope: four refusal producers in the same file pass an authored English sentence positionally to the diagnostic-invariant error, whose registered code declares a message key those sentences render structurally dead. They are the same defect class this campaign is migrating, but they are internal model-validator invariants rather than operator-facing refusals, and the module's existing invariant tests assert on English fragments of exactly those sentences, so migrating them is a coupled change to producers, locale catalogues in four languages, and those tests together. They belong to the campaign-wide reconciliation row rather than to this Step, which names the active-session producer specifically.
- The deferred cross-layer import gate is red at HEAD on an unrelated surface, naming a calc-sheets export service function. That file carries no commit history, so it is an in-flight peer change, not this Step's. This Step's own allowlist entry is unchanged and its function still defers its cross-layer import as declared.
- Nothing could be committed. The repository index lock has been held by a dead process since the previous evening, and it was left untouched as required, so this work is on disk and uncommitted.
- No carry-forward.
