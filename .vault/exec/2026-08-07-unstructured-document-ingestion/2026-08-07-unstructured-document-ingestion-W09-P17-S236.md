---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ae2bef2644e11bdcf4b9804cb0fcd3878f69131c243a5f65c397b37d15e9da2c'
step_id: 'S236'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Decide the anchor search's matching rule for short codes, since closing the markup route narrowed the class rather than eliminating it. Measured against the same country-less UBL document through the same entry point: ID is now unanchored, and ES ANCHORS by matching inside the VAT identifier ESB12345674, while SL anchors against a company suffix. ES is the worst possible value for this to hit since it prefixes every Spanish VAT identifier. Measured as unreachable today rather than assumed, because every country reader returns its own element's text or None and the provenance builder skips a field the record did not state, so no structured reader can emit a country the document lacks. But THE GUARD IS THE PARSER, NOT THE ANCHOR CHECK, while the anchor check's own docstring claims it catches a reader that pointed at an element the document does not carry, which for a two-letter code it demonstrably does not. That is a live gap between a documented property and the behaviour, masked by a guard in a different module. Closing it changes the matching rule to be boundary-aware beyond numeric edges, which is a decision rather than a patch, and it interacts with the deliberate ES-inside-ESP acceptance on the Facturae path

## Scope

- `src/cadrumo/application/ledger`

## Description

- Reproduce the short-code defect against the real matcher and the real
  structured grounding entry point, rather than reasoning from the row.
- Widen the anchor search's boundary rule from numeric edges to word-shaped
  edges, so a two-letter code cannot match inside a longer alphanumeric token.
- Keep the numeric edge rule exactly as it was, which the suite forced: the
  symmetric rule written first refused a figure abutting a currency code.
- Correct the entry point's contract, which claimed a property the check did not
  have, and the structured provenance comment describing the old behaviour.

## Outcome

Modified: `src/cadrumo/application/ledger/_grounding_anchor.py`,
`src/cadrumo/application/ledger/tests/test_grounding_anchor.py`, and the
structured provenance comment in `src/cadrumo/application/ledger/_evidence_draft.py`.

**The decision the row asked for: widen the matcher, do not narrow the
docstring.** A fragment is not evidence, which is exactly why the numeric rule
exists, and restricting it to numeric edges was an under-generalisation rather
than a design boundary. The reasoning recorded for the restriction -- that a
word-shaped anchor is distinctive enough for substring matching -- holds for an
invoice number or a party name and collapses for a two-letter code. Narrowing the
contract instead would have left the documented property enforced only by a guard
in another module, which is a property that stops holding the moment that module
changes and nothing reports it.

**The interaction the row flagged does not exist, and the brief had it
backwards.** The Facturae path anchors on the form the record STATES, `ESP`,
which is a whole token in its own text, and re-derives the carried `ES` from it.
It never depended on `ES` matching inside `ESP`. The comment at that call site
describes that substring hit as an accidental one the pairing was built to route
around, so it is documented as a defect worked around rather than as a deliberate
acceptance to preserve. Measured after the change: the Facturae pairing still
resolves anchored, and the accidental hit is now impossible rather than merely
avoided.

Measured through the real matcher and the real structured entry point, before and
after. Before: `ES` anchored against `ESB12345674` on a record stating no country,
producing an `anchored` envelope. After: the same call resolves `unanchored` with
the offered form preserved as a refusal, while a record that really states `ES`
still anchors.

**The asymmetry was found by the suite, not reasoned.** The first rule applied
alphanumeric boundaries to both edge kinds and refused `100,00` against
`Total EUR100,00 pagado` -- a currency code abutting a figure is a unit, not more
of the figure. The rule is now asymmetric by design: a numeric edge continues only
into number characters, a letter edge continues into any alphanumeric.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m "unit or integration"
    1 failed, 1267 passed, 16 warnings in 331.14s (0:05:31)

The single failure was `test_counterparty_establishment.py::test_a_prefixed_foreign_identifier_addresses_a_record_without_a_stated_country`,
raising `AttributeError: type object 'IvaTerritorialScope' has no attribute
'EU_MEMBER_STATE'` -- a concurrent enum rename caught mid-edit in a file carrying
41 uncommitted lines. Re-run on its own once the peer had corrected it:

    uv run --no-sync pytest "src/cadrumo/application/ledger/tests/test_counterparty_establishment.py::test_a_prefixed_foreign_identifier_addresses_a_record_without_a_stated_country" -n0 -q
    1 passed in 1.19s

The owning suite plus the structured provenance suite, on a tree byte-identical to
HEAD for both files this Step commits:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_grounding_anchor.py src/cadrumo/application/ledger/tests/test_structured_path_provenance.py -n0 -q -m "unit or integration"
    55 passed in 8.28s

Mutation-proved from outside the repository, each asserting the matcher's own
verdict changed before reporting: reverting to the numeric-only rule reds 3 cases,
and restoring the symmetric rule reds 3 including the pre-existing currency case.

## Notes

The structured provenance comment correction could not be committed. That module
carries an unrelated uncommitted peer hunk, so a pathspec commit would take their
content and a bare commit would additionally take a foreign file already staged in
the index. The edit was staged through the apply-cached drive, confirmed to carry
only this lane's hunk, then reversed rather than committed with a peer's work
attached, and applied to the working tree instead for a sweeper to land. Their
hunk is intact.
