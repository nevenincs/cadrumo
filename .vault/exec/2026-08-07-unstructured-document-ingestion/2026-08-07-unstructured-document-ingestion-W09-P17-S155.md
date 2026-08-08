---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:278a7ed076402a81da21c97d94dd528c38b78333afdad351b2376716f35af8ce'
step_id: 'S155'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Declare the two party facts as a closed `PartyFact` axis in the IVA classification substrate: the VAT identification state, and territorial establishment under LIVA arts. 69-70.
- Add a domain resolver that reads the identifying Member State off a printed VAT number, in its own module beside the establishment resolvers rather than inside them, because the two answer different questions from the same evidence.
- Split the criteria model: the residency fields carry establishment only, and the former `*_member_state` fields become `*_identification_state`, optional independently of the residency.
- Remove the model validator that made an EU establishment demand an identification state; that coupling was the conflation in structural form.
- Declare per rule which facts the branch consumes, with the intra-community families the only ones consuming the identification, and stamp the declaration on every classification result.
- Declare both facts consumed on the fallthrough sentinel, so an operation no rule places is asked rather than certified as needing nothing.
- Key the domestic rate lookup on the issuer's establishment instead of its identification state.
- Resolve the identification in the producer from registration evidence or an explicit assertion, never from the printed address country, and demand it only where the reached branch declares it consumed and only for the counterparty, since the filer's own registration is a profile fact.
- Carry both identification states on the declared-facts channel as fields, not a second supply route.

## Outcome

Two facts where there was one, consumed separately and demanded independently. A printed foreign prefix is now decisive for identification and settles nothing about place; symmetrically, no registration on either side settles place. The intra-community population still resolves with no operator question, because the printed number supplies the fact those branches actually turn on, while a domestic invoice is never asked for a number its treatment does not consult.

Two design corrections surfaced from the gates rather than from review. The first demand implementation asked for BOTH parties' identification; the declaración recapitulativa reports the counterparty's NIF-IVA and the filer's own registration is a profile fact, so the demand is now scoped to the counterparty by direction. The second was the accumulate-at-once branch, which reported the identification before any branch was known and so would have put a NIF-IVA question on every domestic invoice lacking a country code; it no longer reports there, and the comment records the tradeoff.

The rate lookup was reading the identification field to answer a question about the territory of taxation. Before the split that was harmless, because the two values could not disagree. After it, a Spanish-established party may legitimately carry a German identification, and the previous fallback would have priced a domestic Spanish supply off the German schedule.

The ladder re-runging is a separate row and was not begun here.

## Verification

Domain and producer gates, unit lane:

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/application/ledger src/cadrumo/application/invoices src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding_reverse_charge.py -n0 -q -p no:randomly -m unit
    6 failed, 1733 passed, 85 deselected, 15 warnings in 115.38s (0:01:55)

The six failures are peer surfaces, triaged and none on this row's files: four on the structured-country lane's in-flight extract payload (`customer_country_code` / `supplier_country_code` present on the draft and absent from the payload), one on a check-registry ordering drift (`postal_code_shape`), one on a vision-escalation case. All fifteen failures this row's change caused were closed.

Integration lane:

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/application/ledger src/cadrumo/application/invoices -n0 -q -p no:randomly -m integration
    85 passed, 1730 deselected in 82.40s (0:01:22)

Six mutations, each installed from an out-of-repo pytest plugin at module scope, each confirmed by its printed banner before the result was read:

- identification derived from a non-registration source: 4 failed, 22 passed
- every branch demands every party fact: 1 failed, 25 passed
- no branch demands the identification: 3 failed, 23 passed
- rate schedule keyed on the identification state: 1 failed, 25 passed
- no branch declares it consumes the identification: 5 failed, 21 passed
- unestablished evidence silently yields an establishment: 3 failed, 7 passed

The last reddens the German case, the Spanish case and the symmetry comparison together, which is what proves the asymmetry gate can fail from either side rather than only from the side that was wrong.

Type checkers and linter report no diagnostic on any file this row touched.

## Notes

A sweeper commit took the domain half of this work mid-flight, at its final state; the producer half, the gates and the stubs were committed here. Nothing was lost and no peer content entered the commit, which was verified after the fact by numstat over its twelve files.

The generated API stub for a peer's landed module was included alongside this row's own, because the two share one toctree file and landing one line without the other would have left the build referencing a stub that does not exist.

One asymmetry is recorded rather than closed: a Spanish identification cannot yet be established from evidence, because Spanish identifiers carry no VAT prefix and route through the Spanish tax-id validator instead. Nothing here infers one from silence, so the gap surfaces as an honest question rather than a wrong value, but the producer currently reaches it only by operator assertion.
