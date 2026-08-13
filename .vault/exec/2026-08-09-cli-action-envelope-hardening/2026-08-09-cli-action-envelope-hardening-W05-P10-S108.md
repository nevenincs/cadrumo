---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e155113260d573dfffce2f652f8ac7e0f02e3b7817561869b17fb5432b9a393c'
step_id: 'S108'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate application invoice-lifecycle recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/invoices/_lifecycle.py`

## Description

- Delete the authored English sentence from all five refusal producers, leaving the locale key and the machine facts.
- Add a regression proving no refusal in the module carries an authored sentence.

## Outcome

- All five producers now raise with a locale key plus machine facts and no authored text. Every key was already present in Catalan, English, Spanish and Hungarian with the right interpolation placeholders, so no catalogue change was needed and no key was added.
- The substantive finding is that the existing tests could not have caught this. They pin each refusal's key and context, and message resolution prefers the key over the positional argument, so an authored sentence passed alongside the key resolves identically and hides. It does not hide everywhere: `str(exc)` prefers the positional argument, so the English still reached tracebacks, logs and every boundary rendering the exception directly, in every locale. An out-of-repo probe showed both shapes resolving to the same Spanish sentence through the message resolver while `str(exc)` differed, which is exactly why the prose survived four otherwise well-formed assertions. The count is four, not five: `test_lifecycle.py:84`, `:92`, `:110` and `:180` pin `translated_message`, while the fifth producer's test at `:301` asserted the exception type alone and pinned no key at all, so it was weaker than the four rather than one of them. That test now pins `application.invoices.lifecycle.errors.empty_invoice_patch` by identity, bringing all five producers to key-level coverage.
- The new regression drives all five refusals through the real services against the real encrypted repository and asserts the absence rather than the identity: with no authored message, `str(exc)` degrades to the key. The same probe confirmed the assertion discriminates, holding for the migrated shape and failing for the regressed shape, so it is not tautological.
- The regression also asserts the five keys are distinct, so a future copy-paste cannot collapse two conditions onto one key, and asserts each key resolves to text different from itself, so a key that never landed in the catalogue fails rather than rendering bare.
- The migration invalidated its own census fingerprints in the recovery rehoming ledger, which keys ownership entries by normalised AST digest. Both entries this Step owns were re-pointed at digests recomputed with the ledger's own normaliser, with their diagnostic locators corrected to the current spans. The ledger writer was not run and no entry outside this Step's ownership was touched. The row's third ownership belongs to a different Step and a different module, and remains stale under its own owner.
- Eleven tests pass in the owning module. Ruff check is clean across the package.

## Notes

- No consumer or test matched any of the five deleted sentences, so the deletion had no reachable dependant.
- The regression does not run in the default per-push lane. The module carries a file-level `pytest.mark.integration`, and the default selection is `unit and not external_tool and not os_keychain`, so a plain run of this file reports all eleven tests deselected and zero executed. The only test of the eleven that catches the injected defect is therefore invisible to the lane that would catch a reintroduction fastest.
- The marker is genuinely earned, not merely inherited: the regression drives two of the five refusals (`remove_linked_invoice`, `empty_invoice_patch`) through `isolated_runtime_profile` against a real encrypted repository, which is integration work by any reading. The remaining three refusals are pure in-memory catalogue resolutions needing no profile, no repository and no key provider. The absence property for those three could therefore be pinned in a `unit`-marked sibling and gain per-push coverage without weakening anything or splitting the integration test. Recorded rather than acted on, since retopologising a peer-authored test module is outside this Step's declared scope. The sibling topics Step's equivalent assertions are `unit`-marked and do run per-push, so the gap is specific to this module.
- The box is deliberately left unchecked. This is a producer-migration row and a rehoming ledger owner. Because the ledger records every construction of an error qualname rather than only prose-bearing ones, migrating the message changes the construction rather than removing it, so the row cannot leave `migration_required` and checking the owner would add to a gate already red at HEAD with 151 `E_REHOMING_OWNER_CLOSED` findings naming twelve already-closed producer Steps. The blocking analysis and the pending decision are recorded in the rehoming ledger owner-closed audit. The ledger writer was not run, no allowlist entry was added, and no closed Step was touched.
- Nothing could be committed: the repository index lock has been held by a dead process since the previous evening and no commit has landed in over five hours. The lock was left untouched as required, so this work is on disk and uncommitted.
- No carry-forward.
