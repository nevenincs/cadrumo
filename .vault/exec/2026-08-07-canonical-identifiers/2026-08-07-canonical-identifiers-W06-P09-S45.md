---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e5ac9753f6da1913ba1e84821eea6f43132a7f19b791603fe4d566811800c7f3'
step_id: 'S45'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# self and profile-owned tax identity: `tax_id`, `spouse_tax_id`, `profile_tax_id` onto `SubjectTaxId`

## Scope

- `src/cadrumo/domain/contribuyente/family.py`
- `src/cadrumo/application/filing/_complementaria.py`
- `src/cadrumo/domain/contribuyente/tests/test_family.py`

## Description

- Two blocking conditions from the team lead resolved BEFORE retyping
  anything, per instruction:
  - `application/auth/_sessions.py`'s `ClaveCredentials.profile_tax_id`
    empty-string default: read the class, found the SAME `""`-default
    convention on 6 sibling fields (`dni_nie`, `numero_soporte`,
    `fecha_validez`, and their `profile_` counterparts) and traced the
    value to `ClaveAuthFacts.tax_id` (also `""`-defaulted), which itself
    documents "a profile that has NOT YET recorded its fiscal identity."
    Confirmed empirically both classes construct fine today with the
    empty default; `SubjectTaxId`'s validator raises "tax identifier is
    empty" on the same input. This is the class's own deliberate
    not-yet-known convention, spanning two classes and seven fields — a
    design question, not this row's to resolve. Left both sites bare.
  - `application/filing/_complementaria.py`'s `_SubmittedOriginal` is a
    `@runtime_checkable Protocol`: typed the attribute for reader
    consistency and documented in the class's own docstring that a
    Protocol attribute carries no runtime validation.
- Re-ran the family/profile-owned population by hand rather than trusting
  the re-sized row's file list: `spouse_tax_id`'s one site
  (`core/setup_answers.py`) shares the exact same empty-string convention
  found in `_sessions.py` — confirmed empirically (`SetupAnswers()`
  constructs fine with `spouse_tax_id=""` today) — left bare for the same
  design-question reason.
- Traced EVERY remaining `tax_id`-named site to its owning class before
  typing, rather than trusting the census name, and found two genuine
  semantic misclassifications the census's per-name search cannot see:
  `adapters/inbound/einvoice/_record_batch.py`'s `AeatParty.tax_id` is
  used for BOTH `issuer` and `recipients` on one e-invoice record — which
  role is the filer's own depends on the record's direction
  (`AeatRecordFamily.SII_FACTURAS_EMITIDAS` vs `_RECIBIDAS`), so no single
  static type is correct for every use. `application/ledger
  /_evidence_draft.py`'s `CounterpartyDraftSide.tax_id` is, by its own
  class name, a counterparty concept wrongly reachable only through the
  self-owned `tax_id` census bucket — it belongs with `W06.P10`'s
  `TaxIdIdentityToken` population despite carrying none of that bucket's
  six counterparty-prefixed names. Left both bare; not this row's to
  redesign or reclassify.
- Retyped `domain/contribuyente/family.py`'s
  `_RentaPersonProfileBase.tax_id`. First attempt looked like a
  regression: constructing with `tax_id=""` after the retype raised
  `SubjectTaxId`'s checksum error. Tested the UNMODIFIED baseline before
  concluding that — `RentaDescendantProfile(tax_id="")` on `HEAD` ALSO
  raises, via the class's own pre-existing `_optional_text_not_blank`
  validator ("optional text fields must not be blank"). Same
  accept/reject boundary before and after, only the message differs (both
  wrap into one `pydantic.ValidationError` at the model boundary, so a
  caller catching that type sees identical behaviour). Confirmed with
  five inputs (`""`, `"   "`, `None`, and two valid NIF/NIE shapes).
- Updated `test_family.py`: two placeholder tax-id literals
  (`"TAXIDABCD"`/`"TAXIDWXYZ"`, never real or checksum-valid, chosen when
  the field was an unconstrained `str`) replaced with checksum-valid
  synthetic NIFs (`"12345678Z"`/`"00000000T"`, verified against the real
  algorithm, not copied from a test run). The blank-rejection test moved
  from `tax_id` to `display_name` (still exercises the shared validator
  it was written for) plus a new test recording `tax_id`'s own blank
  rejection through the checksum validator specifically, so coverage for
  that accept/reject boundary is not silently dropped by the field
  switch.

## Outcome

COMPLETE. 2 of the row's 7 re-sized sites retyped; the other 5 correctly
left bare, each with a concrete, empirically-demonstrated reason (2
design-question, 2 semantic misclassification, and — trivially — none
left undecided). `ruff check`, `ruff format --check`, `basedpyright`
clean on `family.py` and `_complementaria.py` (both gated). 34 tests
green across `test_family.py`, `test_family_parse_date.py`, and
`test_complementaria.py`/`test_complementaria_repository.py`; the 4
remaining `test_complementaria.py` failures are a pre-existing
`justificante_csv` pattern mismatch already flagged this campaign (`W02`
territory), confirmed unrelated by content (no `tax_id`/`SubjectTaxId`
reference) and by `git status` (implicated files clean, not this
session's).

## Notes

No incidents. The two semantic-misclassification findings
(`AeatParty.tax_id`, `CounterpartyDraftSide.tax_id`) are a fourth,
distinct census-instrument defect beside under-counting, the unreliable
`verified` marker, and mixed-population counts: a field literally named
after the bucket the census matched it into can still carry the WRONG
role, invisible to a name-based search in either direction. Neither site
is retyped by this row or `W06.P10`; both need their own design decision
(split the type, split the class, or resolve per call site) before either
bucket can claim them.
