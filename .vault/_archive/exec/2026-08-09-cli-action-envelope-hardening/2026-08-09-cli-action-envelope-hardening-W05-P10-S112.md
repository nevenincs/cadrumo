---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:31ab79764648d9d001e5ecbf0d81b12a8363188d550d270e39f72f26d52595ac'
step_id: 'S112'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate core topics recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/core/topics/__init__.py`

## Description

- Replace the slug-lookup refusal's English f-string with the registered refusal key and the rejected slug as a machine fact.
- Replace the empty-catalogue refusal's English f-string with its own new locale key and the resolved catalogue root as a machine fact.
- Add the `core.topics.errors.catalogue_empty` leaf to all four catalogues through the locale CLI.
- Strengthen the unknown-slug test from a prose regex to the registered code, the key and the context facts.
- Add the first real test for the empty-catalogue branch, driven through the loader against a real empty directory.

## Outcome

- Both producers in the declared module now carry a locale key plus machine facts and no authored sentence.
- The substantive finding is that the registered catalogue value was structurally dead. `resolve_error_message` ranks a positional `args[0]` above the registry `message_key`, so both sites short-circuited on their own English string and the registered `REFUSED_TOPIC_NOT_FOUND` message key could never render. A Catalan, Spanish or Hungarian operator received English. An out-of-repo probe confirmed the old shape resolving to `topic not found: 'not-a-real-topic'` independently of the selected locale, and the migrated shape resolving through the catalogue.
- The two conditions were deliberately given separate keys rather than one. An empty bundled catalogue is a packaging defect, not a mistyped slug, and rendering the not-found sentence for it would have misdescribed the failure to the operator. Only one new key was needed because the slug-lookup site reuses the key its registered code already declares.
- The empty-catalogue branch had no test at all before this Step; it is now exercised through the real loader against a real empty directory, not a patched fingerprint.
- The unknown-slug test previously matched `topic|not|found`, which the migrated key text still satisfies by accident. It now asserts the registered code, the exact key and the exact context mapping.
- A later review corrected this record's original claim that pinning the code, key and context makes a regression to authored prose fail. It does not. Message resolution prefers the key, so a sentence passed positionally alongside the key resolves identically and hides; an out-of-repo mutation re-introducing prose at both raise sites left all eight tests passing at exit 0. The prose is not hidden everywhere: `str(exc)` prefers the positional argument, so it still reaches tracebacks, logs and every boundary rendering the exception directly, in every locale.
- Both producers now additionally assert the absence rather than the identity, mirroring the form proven on the sibling invoices Step: with no authored message `str(exc)` degrades to the key. Re-running the same out-of-repo mutation now fails two tests at exit 1, each naming the exact re-introduced sentence, so the tests discriminate and are not tautological.
- The two migrations invalidated their own census fingerprints in the recovery rehoming ledger, since the ledger keys ownership entries by normalised AST digest and the migrations changed both ASTs. Both entries were re-pointed at the recomputed digests with their diagnostic locators corrected to the current spans. The digests were recomputed with the ledger's own normaliser rather than transcribed. The ledger writer was not run.
- Eight tests pass in the owning module, in the default per-push lane rather than behind an integration marker. Ruff check and format are clean across the package.
- A second review found the separate-key decision above only half-implemented, and closed it. Giving the empty-catalogue condition its own locale key while still raising `TopicNotFoundError` left the envelope emitting `REFUSED_TOPIC_NOT_FOUND` for a packaging defect, and pointed `translated_message` at `core.topics.errors.catalogue_empty`, which is not the registered key of the class raised — so the divergence the Step set out to remove survived at the code axis while looking closed at the text axis.
- The condition now carries its own class, `TopicCatalogueEmptyError`, registered as `REFUSED_TOPIC_CATALOGUE_EMPTY` against `errors.refused.refused_topic_catalogue_empty`, with `topic_count` beside the catalogue root so the fact set states the observation rather than only the location. The hand-picked `core.topics.errors.catalogue_empty` leaf was removed from all four catalogues through the locale CLI, and the new key set through `set-batch`; `scaffold --check` reports all four clean.
- The empty-catalogue test now asserts the registered code alongside the key, the facts and the `str(exc)` absence proof, so a future re-merge of the two identities fails rather than passing on the shared class.

## Notes

- The box is deliberately left unchecked. This is a producer-migration row and the rehoming ledger owns two constructor rows for this module keyed to this Step. Because the ledger records every construction of an error qualname, migrating a message changes the construction rather than removing it, so the row cannot leave `migration_required` and checking the owner would add findings to a gate already red at HEAD with 151 `E_REHOMING_OWNER_CLOSED` results naming twelve already-closed producer Steps. The blocking analysis and the pending decision are recorded in the rehoming ledger owner-closed audit. The ledger writer was not run, no allowlist entry was added, and no closed Step was touched.
- Nothing could be committed. The repository index lock has been held by a dead process since the previous evening and no commit has landed in over five hours; the lock was left untouched as required, so this work is on disk and uncommitted.
- The locale parity and honesty gate modules report five failures, none of them from this Step: four are product-branding heading divergences and one is 804 missing Spanish M303 casilla labels owned by the casilla-schema campaign. The new key appears nowhere in that output.
- Deferred, deliberately not fixed here: the two conditions carry distinct locale keys but the same exception class, so both resolve to the single registered code `REFUSED_TOPIC_NOT_FOUND` in the `REFUSED` category, whose own registered `message_key` is `errors.refused.refused_topic_not_found`. A machine consumer reading the envelope therefore cannot distinguish "the operator mistyped a slug" from "the shipped wheel contains no topic catalogue at all", and a packaging defect reports under a code and a default message key that literally read *topic not found*. The human-facing text is correct in both cases because each raise site carries its own key; the defect is confined to the code axis. Separating them means adding a code to the registered taxonomy and to the operator-visible exit-code surface, which is an ADR decision rather than an executor's call, so the taxonomy was left untouched. Raised for a decision record.
- Carry-forward: the taxonomy split above.
