---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0d4500e59e44dbc8950cb9d97267298370c577bc2349416b3c990f8d1d70ca7c'
step_id: 'S138'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Assemble the counterparty establishment ladder

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add the identifier rung to the domain establishment resolver as a pair, `country_code_for_printed_tax_identifier` and `territorial_scope_for_printed_tax_identifier`, matching the printed number's leading pair against the closed VAT prefix vocabulary and its body against that State's published VIES structure.
- Add `iso_country_for_nif_iva_prefix` to the identity authority, so Greece's `EL` prefix reaches the ISO-keyed catalogues as `GR` rather than falling outside the Member States.
- Add `_establishment_ladder.py` carrying `EstablishmentRung`, `CounterpartyEstablishment` and `resolve_counterparty_establishment_scope`, walking the four rungs and stopping at the first decisive one.
- Read a positively established Spain from the country CODE rather than the country rung's scope, so the documented Spanish refusal opens the postal rung instead of ending the ladder.
- Consult the confirmed-fact store on every call, decisive page or not, so a disagreement between an operator's remembered assertion and the printed evidence is carried as a contradiction with no scope.
- Rename the sibling Spain predicate from `_names_spain` to `names_spain` and consume it rather than restating it, so one authority decides what opens the postal rung.
- Promote the criteria assembly, the declared-fact channel and the classifier inputs onto the package facade, the precondition the ladder's own consumers need.

## Outcome

The ladder answers in the order the ruling sets and yields nothing when it exhausts. All six independently measured compositions reproduce: a Spanish name with a Las Palmas code resolves to Canarias through the postal rung, a Madrid code to the mainland, a Spanish name with no postal code exhausts, and a French or German name resolves through the country rung without the postal rung ever being consulted. A postal code with no country evidence exhausts rather than resolving to the peninsula.

The identifier rung refuses both Spanish spellings. A bare CIF and an `ES`-prefixed number are both checksum-valid statements about where a party is REGISTERED, and establishment for IVA is the sede de actividad económica, so neither opens a rung and neither is read as naming Spain. Only the printed address country can do that. The rung also refuses a prefix carried on arbitrary text, because two leading letters are not a VAT number and would otherwise place a party in France.

A corrupt bundled table raises out of the ladder untouched. No rung is wrapped in a bare except, so a broken data file stays distinguishable from a counterparty whose territory nobody established.

## Verification

Sequential, and both marker lanes reported because a selection that matches nothing exits zero.

    uv run --no-sync pytest -n0 -q src/cadrumo/application/ledger/tests/test_establishment_ladder.py
    28 passed in 3.78s

The wider surface the change touches, under the default marker expression:

    uv run --no-sync pytest -n0 -q <ladder, counterparty establishment, classification assembly, declared facts, structured postal, domain iva tests, core identity tests>
    676 passed in 22.70s

The integration lane over the same paths selects nothing, and says so rather than reading as green:

    uv run --no-sync pytest -n0 -q -m integration <same paths>
    657 deselected in 0.80s

Three mutations, each installed from a plugin module outside the repository and each confirming its own banner before the run:

- Exhaustion falls back to the mainland: 13 failed, 13 passed. The whole-enum sweep, the bare domestic invoice, both exhausting measured cases and the unrecognised-name case all redden; the French and German cases stay green legitimately, because the mutation cannot reach a decisive rung.
- The postal rung is consulted first and ungated: 9 failed, 17 passed. Both foreign-postal ordering cases redden, as does the identifier-outranks case. The two Spanish cases stay green legitimately: postal-first reaches the same territory there, which is exactly why an ordering assertion needs a case where the skipped rung would disagree.
- A bare except around the rung walk: 2 failed, 26 passed.

The third mutation initially ran fully green with its banner confirmed, which was a real gap rather than an inert patch: the one refusal case injected before the ordered walk began, so an except inside the walk swallowed nothing it asserted on. Two further refusal cases were added, one at the first rung and one at the last, and the mutation then bit.

## Notes

The ladder has no production caller, and this is unchanged by the row rather than introduced by it: the criteria assembly's issuer and customer country parameters were already test-supplied only. Nothing routes a document's parties to the ladder by direction, so which party is the counterparty is still undecided in production. That wiring has no row.

The identifier rung's treatment of an `ES` prefix is a judgment made here and worth a second reading. The ruling names the rung as a FOREIGN prefix and separately rejects reading establishment from a Spanish registration, so an `ES`-prefixed number contributes nothing and does not open the postal rung; only a printed address country does. The direction of the choice is safe, since it can only produce an honest unknown, never a wrong territory.

The identifier rung's structural check overlaps in shape with the grounded-identifier re-validation in the reading package. The two answer different questions, one grounding a transcribed value and one naming a country, and neither reaches the other's private module.

Two gates were already red at HEAD from surfaces outside this change and stayed red at the same signatures: the import-linter reports pre-existing application-to-llm and application-to-adapters edges naming no module from this row, and the import-hygiene test-debt count is unchanged at 88 current against 82 documented, with none of the six undocumented sites belonging here. The facade module carries two pre-existing lint findings, an unsorted import block and an unsorted `__all__`, identical in rule and count before and after this change.

A sweeper commit took this row's source files mid-session. The source landed intact; an earlier revision of the gate file was captured with it, and the working revision followed in its own commit.
