---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c1054c4287f13e68ae2c1e9dd9d47166968b0848584b0fe9f2e4cbfd84b8adf8'
step_id: 'S178'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Surface a stated country code the vocabulary does not carry, since the resolver returns nothing for it and the provenance builder skips a null pair, so the operator sees an absent country and nothing else, indistinguishable from a record that stated none. That is precisely the failure the required alpha-3 column exists to close, reproduced one layer up where no refusal guards it. Emit the degradation through the notice channel already extended into the extract envelope, naming the unrecognised code, or attach an unanchored-equivalent envelope. Silence is the one outcome that should not be available

## Scope

- `src/cadrumo/application/ledger`

## Description

- Carry each party's verbatim stated country token on the draft, beside the
  resolved alpha-2 the bundled vocabulary produces.
- Ground the stated token as a copied structured value, so an unplaceable
  country earns a provenance envelope naming the element it was read from.
- Add the record-token status authority to the domain, admitting both ISO
  spellings, and route the country advisory through it.
- Carry the stated token onto the counterparty side and classify it at confirm,
  which is what makes the declared-relief guard's sparing reachable.
- Route the ISO user-assigned alpha-3 ranges to the unassigned kind.
- Project both stated fields onto the extract payload.
- Repoint the advisory fixtures at the field a document can actually populate.
- Add the end-to-end gate, in both spellings and both directions, with its probe
  selected from the vocabulary rather than pinned to one country.

## Outcome

The structured reader's country lookup returned nothing for two different
events -- the record stated no country, and the record stated a token the
bundled vocabulary does not carry -- and both left the resolved alpha-2 field
empty. Downstream, empty meant no provenance envelope and no advisory, so an
unplaceable country was byte-identical to a document with no address block.

That was the visible half. The larger half was a correctness guard being
silently disabled. A guard withholds a declared export or intra-community
relief whose counterparty residency was not established, and it spares the case
where a well-formed code names a jurisdiction our own vocabulary merely lacks --
our gap, not the document's. Its own docstring calls that sparing the difference
between a guard and a trap. Production classified the counterparty's code off
the resolved draft field, which is empty for precisely the codes the exemption
exists for, so the sparing could never fire and every legitimate export naming
an uncatalogued country was refused. The guard's tests supplied the status
directly, so the logic was proven and the wiring was not.

The record's own token is now carried verbatim on the draft, on a field separate
from the resolved one. Putting a three-letter token into a field contracted as
alpha-2 would have traded a silent absence for a silent lie, and every consumer
keyed on the resolved form would have inherited it. The token earns an ordinary
structured envelope, the advisory reads it, and the confirm path classifies it
into the guard.

The classification lives in the domain rather than in the ledger layer, as one
function two consumers share. The printed-value status axis answers only about
alpha-2 and correctly declines to call an address line a bad country code; a
structured record's country element is schema-typed, so the record-token sibling
admits the alpha-3 spelling Facturae states. Its alpha-3 user-assigned ranges
are judged from a reserved-range set rather than from length, because the
catch-all otherwise reported a reserved code as a gap in our data -- the
opposite operator instruction, and one that ends in ungrounded registry data.

Visibility is not placement. The stated token does not reach the establishment
ladder, so an unplaceable country still resolves no territory. The side
attribute carrying it is named a token rather than a code precisely because the
ladder takes a same-named parameter wanting the resolved form: two same-shaped
attributes on one object, one safe in that slot and one not, is a swap that
type-checks.

Modified files:

- `src/cadrumo/domain/iva/_establishment.py`
- `src/cadrumo/domain/iva/__init__.py`
- `src/cadrumo/application/ledger/_evidence_draft.py`
- `src/cadrumo/application/ledger/_confirm_establishment.py`
- `src/cadrumo/application/ledger/_country_vocabulary_advisory.py`
- `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`
- `src/cadrumo/application/ledger/tests/test_structured_country_degradation.py` (new)
- `src/cadrumo/application/ledger/tests/test_country_vocabulary_narrowing.py`
- `src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_country_cli.py`

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva src/cadrumo/adapters/inbound/einvoice -n0 -q -m unit
    1954 passed, 26 deselected, 16 warnings in 160.67s (0:02:40)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_country_degradation.py -n0 -q -m unit
    21 passed in 10.88s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -q -m integration
    163 passed in 48.71s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_country_cli.py -n0 -q -m integration
    5 passed in 8.61s

Four mutation probes, each loaded from outside the repository as a pytest plugin
so nothing under the source tree changed, each rebinding the name in the
CONSUMING module because a definition-site patch would print APPLIED and reach
nothing, and each judged on the gate going red rather than on the banner.

Neutering the status the confirm path's relief exemption is keyed on:

    [MUTATION APPLIED] confirm-path record_country_code_status neutered
    2 failed, 19 passed in 11.20s
    [MUTATION] neutered status called 5 times

Neutering the status the country advisory is keyed on:

    [MUTATION APPLIED] advisory-path record_country_code_status neutered
    4 failed, 17 passed in 13.03s
    [MUTATION] neutered advisory status called 14 times

Dropping the record's stated token on the way to the draft, which restores the
original defect end to end:

    [MUTATION APPLIED] _stated_country_code dropped
    9 failed, 12 passed in 10.90s
    [MUTATION] dropping reader called 38 times

Emptying the ISO alpha-3 user-assigned ranges, which restores the misrouting a
reserved code took before this change:

    [MUTATION APPLIED] _USER_ASSIGNED_ALPHA3 emptied (was 1092 codes)
    1 failed, 20 passed in 11.21s

Under every probe the stated-no-country cases stay green, which is what makes
each red an observable change in the distinction rather than a broadly broken
run.

## Notes

The gate was first written against Thailand, which was measured uncatalogued.
Another lane enrolled Thailand while this row was in flight and the country
vocabulary was observed changing size twice inside one session, at which point
eight cases failed for a reason unrelated to the behaviour under test. The probe
is now selected from the vocabulary at run time by the property it needs --
carried in neither spelling -- and an anchor class asserts the selection still
means what it says, so a future enrolment produces one named red pointing at the
candidate list rather than a suite that quietly stops exercising its subject.

Two findings were raised in review and both are closed here: the ISO alpha-3
user-assigned ranges misrouting to the catalogue-gap kind, and the counterparty
side attribute colliding by name with an establishment-ladder parameter that
wants the resolved form. A third review finding reported the domain classifier
as a duplicate of a peer's uncommitted work; it was this row's own in-flight
promotion, seen mid-session, and there is one definition.

Two things are reported rather than changed. The declared-relief guard's
exemption is keyed on the counterparty's country status but suppresses the
refusal even when the FILER's residency is the missing one, so an uncatalogued
counterparty spares a filer-side gap; that is the guard's own scoping and
predates this row. And the establishment ladder's own parameter is named for a
stated code while receiving the resolved one, which is confusing at its
definition site as well as at the call site renamed here.

Three-letter tokens that are plainly not countries -- a currency code, a totals
marker -- classify as a catalogue gap. That is deliberate and documented: the
element is schema-typed as a country code, so a token that is not one is a
document defect worth naming rather than silence.

No new operator string was introduced: the two existing country notice codes and
their four locale catalogues carry the report unchanged.
