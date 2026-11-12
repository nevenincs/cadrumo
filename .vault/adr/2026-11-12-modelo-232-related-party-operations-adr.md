---
tags:
  - '#adr'
  - '#modelo-232-related-party-operations'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:8d3a0f96b69fa1835e8adf76129e9a9c12f654c60df0e6a40c14b7182ff44f70'
related:
  - "[[2026-09-23-calendar-obligations-payer-fact-declaration-state-adr]]"
  - '[[2026-11-12-modelo-232-related-party-operations-research]]'
---
# `modelo-232-related-party-operations` adr: `Related-party operations fact for Modelo 232` | (**status:** `proposed`)

## Problem Statement

Modelo 232 is owed only on grounds set by Orden HFP/816/2017 art. 2 (`orden-hfp-816-2017:art-2`):
- operations with the same related person or entity above 250.000 euros in the tax period (2.1.a);
- specific operations of one type above 100.000 euros (2.1.b);
- operations of the same type and valuation method above 50% of turnover (2.3);
- the LIS art. 23 intangibles reduction on income from related persons (2.4);
- operations or securities in a tax haven, whatever their amount (2.5).

The rule `modelos/232/revisions/2016-2017/applicability/0001-declarations.toml` tested the entity type alone, so every company was told it owes 232. The coordinator's order of 2026-11-12 19:04 made the verdict INCOMPLETE until a related-party fact is stated, and the thresholds became dated, cited parameters of that revision. No profile or ledger record says whether a taxpayer has related-party operations, so 232 can never leave INCOMPLETE. This record decides what the stated fact is before any field is persisted.

## Considerations

- The payer-fact contract of `2026-09-23-calendar-obligations-payer-fact-declaration-state-adr` gives a dated payer fact three states: declared yes, declared no and undeclared. It also admits derived payer facts that read stored records (fact 0139, for example `exceeds_third_party_threshold` read from the Modelo 347 ledger).
- A yes/no answer would ask the filer to apply art. 2 themselves, the 50% test and the per-person aggregation included. The thresholds are registry data, so the application can apply them to facts the filer states.
- The grounds are per tax period: each ejercicio has its own operations, and the obligation of one year says nothing about another.
- The same facts are what the 232 records themselves carry (counterparty, kind, amount, valuation method), so a later filing route can read them, not a second copy.
- Turnover (cifra de negocios) is needed only for the 2.3 ground. Where it is unknown, that ground stays undecided rather than read as not met.

## Considered options

- **A declared yes/no payer fact "has operations above the 232 thresholds". Rejected.** The filer would apply the art. 2 thresholds by hand, and a wrong "no" would be a silent not-applicable.
- **Typed related-party operation records per ejercicio, plus a stated "none" for an ejercicio, with a derived payer fact that applies the registry thresholds. Kept.** The application decides from stated facts, and every ground and threshold stays registry data.
- **Read related parties from the ledger's counterparties. Rejected.** Being related (LIS art. 18.2) is a relationship the ledger does not record. A counterparty name proves nothing about it.

## Constraints

- No field is persisted before this record is accepted. Persisting one needs a profile schema version bump with a forward, idempotent, tested migration under the payer-fact contract. No stored value is backfilled.
- Thresholds, the turnover share and the grounds are read from the registry parameters of the pinned revision (`modelo-232-same-related-party-threshold-eur`, `modelo-232-specific-operations-threshold-eur`, `modelo-232-same-type-turnover-share`). No consumer restates them.
- Undeclared stays INCOMPLETE. Only a stated "none" for the ejercicio, or stated operations below every threshold with no tax-haven and no intangibles ground, gives NOT_APPLICABLE.
- Operations between members of one tax consolidation group, and the other exclusions of art. 2.2, are stated on the record and left out of the totals. They are never inferred.

## Implementation

We will add one typed record of a related-party operation, owned by the taxpayer's profile and keyed by ejercicio. It carries:
- the counterparty, by tax identifier and filing name, with its LIS art. 18.2 relationship;
- the operation kind: general, one of the art. 2.1.b specific types, intangibles reduction or tax haven;
- the valuation method;
- the amount in euros at market value;
- the ejercicio;
- whether an art. 2.2 exclusion applies.

A separate per-ejercicio statement records that the taxpayer had no related-party operations and no tax-haven operations.

A derived payer fact, declared in fact 0139, reads those records for the ejercicio:
- it answers yes when any art. 2 ground is met under the pinned parameters;
- no when the year's operations are stated (or stated as none) and no ground is met;
- undeclared otherwise.

The 232 rule then requires that fact, and the INCOMPLETE exclusion added on 2026-11-12 keeps its reason for the undeclared state. The ejercicio reaches the rule through the per-period companion mechanism of the payer-fact ADR. The 2.3 ground reads the stated turnover, and leaves the fact undeclared when turnover is unknown and only that ground could apply.

CLI, TUI and window doors to state, list and withdraw the records follow the existing profile record operations. Frontends render served words only.

## Rationale

The order asks for the counterparty, kind, amount and ejercicio. Those are the facts art. 2 tests, and they are what the declaration lists. Applying the registry's thresholds to them keeps the law in data and leaves the filer only facts they know.

## Consequences

- A company that states its related-party operations gets a decided 232 verdict and, when owed, a calendar row. One that states nothing keeps the INCOMPLETE reason.
- A profile schema bump and migration are needed when the record is built, under the payer-fact contract.
- The records are a ready source for a later 232 filing route, which this decision does not build.
