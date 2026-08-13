---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:de1187117b1cca6fa313296177eabfade680115cda9a6340397162aef468885b'
step_id: 'S105'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate domain invoice, IVA, and portal exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/domain/invoices/_service.py`
- `src/cadrumo/domain/iva/_lookup.py`
- `src/cadrumo/domain/portals/_registry.py`
- `src/cadrumo/domain/invoices/_enums.py`
- `src/cadrumo/domain/invoices/_models.py`
- `src/cadrumo/domain/iva/_classification.py`
- `src/cadrumo/domain/iva/_saturation.py`

## Description

- Inventory every refusal producer in the seven declared modules by AST, separating constructor sites from reference sites and flagging those passing a positional argument.
- Delete the authored English sentence from seven IVA refusal producers, leaving a registered locale key and machine facts.
- Split the coverage-versus-legality distinction in the invoice rate-slot resolver onto two distinct keys plus a machine fact.
- Add six locale keys with real values in Catalan, English, Spanish and Hungarian.
- Add absence regressions asserting each migrated refusal renders as its key, and prove they bite under an out-of-repo injection of the defect.
- Classify the producers that were not migrated and record who owns them.

## Outcome

- Seven producers migrated. Two rate lookups and three catalogue-citation refusals in the IVA lookup module, and the two rate-slot refusals in the invoice enum module, now construct with a locale key plus machine facts and no positional argument. No calculation, rate, threshold, saturation rule or category semantics changed; only the refusal messages did.
- The coverage-versus-legality distinction the rate-slot resolver exists to draw previously lived only in an English f-string, so a Catalan, Spanish or Hungarian session lost it entirely at every boundary rendering the exception directly. It now rides two distinct keys and the `rate_registry_covers_date` machine fact, so it survives translation.
- Six locale keys added, each with a genuine translation in all four catalogues and no two locales identical: `errors.iva.rate_member_state_unregistered`, `errors.iva.rate_registry_coverage_gap`, `errors.iva.rate_slot_not_in_force`, `errors.iva.cite_requires_catalogue_or_date`, `errors.iva.category_has_no_legal_basis`, `errors.iva.citation_legal_reference_absent`. Two conditions kept their class's registered message key, which is correct where the class carries exactly one operator meaning; the other four needed their own because their classes carry several.
- The absence assertion is `assert str(caught.value) == "<key>"` for each of the seven sites. It discriminates where a key-and-context assertion cannot: injecting the regressed shape from outside the repository, by wrapping the three exception classes' constructors in a plugin that lives outside the tree, reds all seven absence tests while every key-and-context assertion in the same run stays green. That is the hiding this Step removes, demonstrated rather than asserted.
- Gate results. The three owning domain packages pass 1105 tests. The four migrated and new test modules pass 33 tests clean and fail 7 under injection. Lint and format are clean on all six changed files. The three type checkers report zero diagnostics in any changed file. The locale key scaffold reports zero missing and zero extra entries for the six new keys in all four catalogues.
- Two of the three rehoming ledger rows this Step owns stop authoring a message. Every construction site of the IVA rate and IVA category error classes is now clean, so those rows' `authors_message` evidence flips false and their owner is no longer required to be open. Their normalised digests changed, so the fingerprint multiset check now fires for both until the ledger is regenerated. The ledger writer was deliberately not run and the ledger file was not edited.

## Notes

- The concrete target evidence named for this Step, the fingerprint multiset finding for the invoice not-found error, is not a producer defect and was not one at the start. All three of that class's construction sites already carry a key and machine facts with no positional argument; the sole in-scope site was migrated by an earlier Step whose ledger entry was never regenerated. The finding is regeneration debt, and the ledger row still records a digest for a one-line construction the module no longer contains. Nothing in the declared scope can clear it.
- The portal producer is blocked, not skipped. Both of its construction sites are inside the declared scope and both pass a positional argument, but that argument is the offending portal identifier rather than a sentence: the English is built inside the exception class's own constructor, which lives in the portal error taxonomy module and is not in the declared scope. Passing the identifier by keyword instead would clear the scanner's flag while leaving the sentence exactly where it is, which is gaming the detector rather than closing the defect, so it was not done. The correct fix is a constructor change in the taxonomy module emitting the already-registered portal key plus a portal fact, and it needs an owner.
- Producers deliberately classified out, stated as classification and not as proof. The invoice model module carries roughly sixty pydantic field-validator refusals, the IVA classification module two, the invoice service module one, and the portal registry nine import-time assembly refusals. All carry authored English. None carries a rehoming ledger row, and all are internal shape or assembly invariants rather than operator-facing refusals, surfaced through pydantic validation rather than the envelope. That reading is defensible but it is a reading: the standing campaign goal asks that every reachable failed precondition emit a stable condition identity, and these do not. If any is reachable from an operator surface it needs its own row. No row currently covers them.
- The two rate-lookup tests that previously pinned rendered prose were rewritten onto key and machine facts. One of them was passing for the wrong reason: its pattern matched the substring "rate", which the replacement key also contains, so it would have stayed green through the migration without ever asserting anything about the condition. It now pins the full key and the exact fact set.
- Three of the catalogue-citation refusals cannot be reached from the bundled catalogue, which is complete by construction, so their regressions drive real frozen catalogue and citation aggregates built in the test. These are real domain models with real validation, not stand-ins.
- Repository-wide gates that are red and not owned here. The relative-import gate reports 59 violations, none in a changed file. The type-check run reports diagnostics across 246 files, none in a changed file. The locale parity, audit and honesty gates fail on the product-identity taglines, the Modelo 303 schema leaves, two dynamic translation prefixes, a dead allowlist entry, and em dashes in TUI keys, none of which this Step touched; the locale scaffold's own missing-key report is entirely in the live-application namespace and belongs to another campaign. A package unrelated to this Step is mid-edit in the working tree and its identity module currently fails to import, which collapsed one gate run; that was confirmed to be peer work in progress and left alone.
- The four locale catalogues are written concurrently by other agents and carried substantial uncommitted peer content. They were landed through the apply-cached drive from a HEAD-anchored own-only patch, verified to add fourteen lines and remove none in each file, so no peer content was taken. The six source and test files were unentangled and diffed clean against HEAD before staging.
- The box is deliberately left unchecked, and no plan verb was run. This Step is a rehoming ledger owner and its migration changes the recorded digests, so the ledger must be regenerated before its rows can settle. The regeneration was explicitly serialised elsewhere.
- Carry-forward: the portal producer's constructor, and a decision on the sixty-odd validator refusals classified out above.
