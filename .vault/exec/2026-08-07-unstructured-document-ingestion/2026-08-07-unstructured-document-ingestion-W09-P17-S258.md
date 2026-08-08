---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8508464d84909eb2b16b2212f569d51b88b53096f2d3fc617ec5c07ff5ac39e2'
step_id: 'S258'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Audit the eight country branches against the ledger-side unknown, since Transaction.counterparty_country is ALREADY nullable so the not-asked state exists today and reaches these consumers - three branch on not-equal-ES and collapse unknown into FOREIGN (_source_resolver 598, _invoice_retencion 368, _issuer_establishment 157) and five branch on equal-ES and collapse it into NOT-DOMESTIC (_counterpart 333, _ledger_catalogue_invoice_payloads 91, domain/invoices/_models 325, _identity_roles 193, _wizard 117) - _counterpart fails CLOSED which is the right direction and the other seven are unmeasured - the persisted Invoice field stays REQUIRED because nullability would add a state no producer creates to solve an import problem S272 already solved

## Scope

- `src/cadrumo/domain/invoices`

## Description

- Audit all eight counterparty-country branches for what an absent country does,
  measured at each consumer's own carrier rather than at a constructed call.
- Pin the persisted counterparty country as required, together with the payload
  normaliser behaviour that depends on it, in a new domain test module.
- Pin that an absent country does not verify a foreign identifier as Spanish, in the
  existing ledger identity-roles tests.
- Change no production code: every site audited is already correct.

## Ruling

The persisted invoice counterparty country STAYS REQUIRED. That ruling was made by the
campaign coordinator, not by this lane, and the distinction matters: the evidence for
it rests partly on this lane's own earlier change, and a lane whose change dissolves
its next row's premise is the least reliable judge of whether that row should shrink.
The row was left open and the coordinator signed it off.

The row's original direction -- make the field nullable so a blank import column
preserves the import -- was correct when written and was overtaken. The import is now
preserved by the importer-side refusal with an explicit whole-import declaration,
which the row had listed and rejected as an alternative on the grounds that it breaks
existing files. With the declaration as recourse it does not break them.

Three things decided it. Nullability would add a state no producer creates. The
attempt to falsify that nearly succeeded -- the e-invoice parser models its country
as optional and documents a document carrying no country element at all -- but that
adapter never reaches the persisted invoice, and its absence already has a home on
the ledger transaction, whose country is optional today. And the counterpart
aggregation lane already faced this exact choice and made its field required, with a
comment recording that an optional field only moves the problem.

## Outcome

Of the eight branches, six cannot receive an absent country at all, because the
carrier they read it from refuses one. That is the ruling's protective effect stated
as a measurement rather than an intention: keeping the persisted field required is
what makes three quarters of the audited surface unreachable.

Two sites do take a nullable country, and both are already correct.

The ledger identity helper falls back to the Spanish path when no country is stated.
That fallback is safe because the Spanish algorithm then REFUSES an identifier that
is not Spanish: a bare foreign number with no prefix to speak for it comes back
unverified rather than canonicalised into a Spanish identity. It fails closed, so it
gets a regression rather than a change.

The invoice payload normaliser forwards the tax id WITHOUT validating it when the
country is not a string, because it has no country to validate against. That is not a
defect today -- the model refuses the record immediately afterwards -- but it is a
defect the moment the field admits absence, because the tax id would then reach
storage having been checked against nothing. The two halves are pinned in one module
so a later reader cannot change one without meeting the other.

A ninth site outside the audited eight is worth recording as the model for the whole
class: the IVA ledger export path already receives the ledger-side absent country,
refuses it explicitly rather than reading it as third-country establishment, and
carries a comment saying that no country recorded is not a place. That is the
treatment the other reachable sites are being held to.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_counterparty_country_is_required.py -m unit -q -p no:randomly
    3 passed in 8.01s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_identity_roles.py -m unit -q -p no:randomly
    19 passed in 16.26s

The requiredness regression was then proven to bite by a runtime mutation driven from
outside the repository, which asserted the field was actually nullable before running
anything:

    window OPEN: Invoice.counterparty_country is now nullable
    FAILED .../test_counterparty_country_is_required.py::test_an_absent_counterparty_country_is_refused_on_that_field
    1 failed, 21 passed in 4.08s

Exactly one test red, and the anti-tautology control asserting that the unmodified
payload validates stayed green, so the refusal is a refusal on the country rather
than a payload that was broken anyway.

## Notes

**An instrument fault in the audit itself, caught before it was reported.** The first
reachability probe reported that the invoice carrier refuses an absent country -- but
the refusal came from a fabricated identity hash, not from the country, so it proved
nothing about the field under audit. Rebuilt through the production builder and
re-validated from the record's own dump with only the country replaced, the refusal
is attributed to the country field by name and is preceded by a positive control
showing the unmodified payload validates. A carrier that refuses for the wrong reason
is indistinguishable from one that refuses for the right one.

**Nothing was fixed, deliberately.** Both reachable sites already take the safe
branch. A site that fails closed needs a regression pinning that behaviour, not a
change; changing it would have produced a diff that looked like work and removed
nothing.

**Not audited, and stated as a limit rather than a clean result.** The six unreachable
sites were proven unreachable at their carrier, which is a statement about the type,
not about every path that constructs one. A future producer that builds any of those
carriers from a ledger transaction without supplying a country would fail at
construction rather than branch silently -- that is the desired direction, but it is
an inference from the carrier rather than an enumeration of producers.
