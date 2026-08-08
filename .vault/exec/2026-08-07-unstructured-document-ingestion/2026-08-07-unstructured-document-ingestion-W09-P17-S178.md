---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:cf5aea256bf3d86ad2af4be700d3b724a33c5c532f9252f801892afd9a11cedf'
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
- Read the country advisory from the stated field, and classify a three-letter
  token the alpha-2 status authority declines to judge.
- Project both stated fields onto the extract payload.
- Repoint the advisory fixtures at the field a document can actually populate.
- Add the end-to-end gate for the distinction, in both spellings and both
  directions.

## Outcome

The structured reader's country lookup returned nothing for two different
events -- the record stated no country, and the record stated a token the
bundled vocabulary does not carry -- and both left the resolved alpha-2 field
empty. Downstream, empty meant no provenance envelope and no advisory, so
`XX`, `ZZ`, `THA` and `TH` were byte-identical to a document with no address
block. Every channel silent, on the reading path handling the most reliable
country evidence in the system.

`TH` is why that mattered rather than merely being untidy. Thailand is absent
from the vocabulary, so it resolves as uncatalogued and not as a third
country: a genuine Thai export arrived carrying no country, its territory
unresolved, and nothing told the operator the document had stated one.

The record's own token is now carried verbatim on the draft, on a field
separate from the resolved one rather than inside it. Putting `THA` into a
field contracted as alpha-2 would have traded a silent absence for a silent
lie, and every consumer keyed on the resolved form would have inherited it.
The stated token earns an ordinary structured envelope -- it really does occur
in the record's text, so it grounds honestly -- and the advisory reads that
field instead of the resolved sibling it could never be populated on.

That last part is the reason the advisory had never fired from a real
document. It read the resolved field, which is empty for precisely the codes
it exists to report, while its own tests set that field by hand. The
classification is unchanged for alpha-2 and borrowed from the domain
authority; the one addition is that a three-letter alphabetic token nothing
places is reported as a catalogue gap, which the alpha-2 authority
structurally cannot answer. That is the route that reaches Facturae, the
Spanish national format, which states the country in alpha-3.

Visibility is not placement. The stated token does not reach the
establishment ladder, so an unplaceable country still resolves no territory --
naming it to the operator must not become a way of settling a third country
from a string with no referent, which on the issued side is zero-rated export
treatment.

Modified files:

- `src/cadrumo/application/ledger/_evidence_draft.py`
- `src/cadrumo/application/ledger/_country_vocabulary_advisory.py`
- `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`
- `src/cadrumo/application/ledger/tests/test_structured_country_degradation.py` (new)
- `src/cadrumo/application/ledger/tests/test_country_vocabulary_narrowing.py`
- `src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_country_cli.py`

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit
    1 failed, 1199 passed, 26 deselected, 16 warnings in 215.91s (0:03:35)

The single failure is `test_identity_roles.py::test_a_document_stating_no_identifier_resolves_to_an_unresolved_role`, whose implementation module carries another lane's uncommitted work; it asserts a role-resolution finding on a draft with no identifiers and no country, and is untouched by this surface.

    uv run --no-sync pytest src/cadrumo/adapters/inbound/einvoice -n0 -q -m unit
    29 passed in 1.49s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_country_degradation.py -n0 -q -m unit
    13 passed in 7.05s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -q -m integration
    163 passed in 48.71s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_country_cli.py -n0 -q -m integration
    5 passed in 8.61s

Two mutation probes, both loaded from outside the repository as pytest plugins so nothing under the source tree changed. Each prints a banner, counts its own invocations, and is judged on the gate going red rather than on the patch landing.

Neutering the advisory's status classifier:

    [MUTATION APPLIED] _stated_code_status neutered
    4 failed, 9 passed in 8.82s
    [MUTATION] neutered classifier called 14 times

Dropping the record's stated token on the way to the draft, which restores the measured defect exactly:

    [MUTATION APPLIED] _stated_country_code dropped
    7 failed, 6 passed in 9.57s
    [MUTATION] dropping reader called 28 times

Under both probes the stated-no-country cases stay green, which is what makes the red an observable change in the distinction rather than a broadly broken run.

## Notes

`_evidence_draft.py`, `_ledger_business_payloads.py` and `test_evidence_draft_provenance.py` all carried other lanes' uncommitted work while this landed, so each edit was rebuilt from `git show HEAD:<path>` and staged through an own-only patch; the working copies keep the peer content untouched.

The advisory's classification of a three-letter token as a catalogue gap is answered in the application layer rather than by widening `stated_country_code_status`. That authority is handed printed values and correctly declines to call an address line a bad country code; a structured record's country ELEMENT is schema-typed, so this layer knows the token is a country-code claim and the domain cannot. If the domain later gains an alpha-3 status answer, this local rung should defer to it.

No new operator string was introduced: the two existing country notice codes and their four locale catalogues carry the report unchanged.

Nothing in this change makes an unplaceable country placeable, and the confirm remains non-blocking on both country conditions.
