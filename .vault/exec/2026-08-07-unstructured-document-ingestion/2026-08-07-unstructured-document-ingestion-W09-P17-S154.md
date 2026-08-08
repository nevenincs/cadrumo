---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:46105d0ecf34783325f0ff4f4fdcbdb6794dd50818bbe2121bb6070e9173233b'
step_id: 'S154'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Ask each party printed country name on the read path, since the field contract asks for both postal codes and both tax ids and no country at all, its postal instruction explicitly excluding the country, so the ladder country rung has no source for the vision and text population and the postal rung gated behind it can never fire for them. Transcribe the printed name verbatim for the bounded vocabulary to match, never an alpha-2 code, because asking a reader for a code is asking it to translate. Same atomic contract widening the postal codes needed across every surface plus fully populated fixtures, so it is the not-started-is-safe shape and must not be begun without room to finish

## Scope

- `src/cadrumo/llm`
- `src/cadrumo/application/ledger`
- `src/cadrumo/entrypoints/cli`

## Description

- Declare `supplier_country` and `customer_country` as `FREE_TEXT` rows in
  `INVOICE_FIELD_CONTRACTS`, each instructing the reader to copy the printed
  country name in the document's own language, never abbreviated to a code.
- Mirror both fields on `ExtractedInvoiceFields` and on `ExtractedFieldAnchors`.
- Ground both in `ground_extracted_fields`: through the declared-form dispatch,
  into the `grounded` map that keys the provenance envelopes, and onto the
  returned draft.
- Carry both on `InvoiceDraft`, documenting that the value is a name and that the
  vocabulary match belongs to the domain resolver.
- Add both to `EvidenceExtractResult`, which the extract command splats the draft
  into under `extra="forbid"`.
- Populate all three fixtures: the anchor fixture with anchors deliberately
  unequal to their values, the contract fixture's fully-populated grounder round,
  and the provenance roundtrip off-default and party-distinct.

## Outcome

The six surfaces landed together. The two parties are independently transcribed,
independently grounded and independently anchored, so an issuer in one country
billing a customer in another is expressible.

The row's purpose — giving the establishment ladder's country rung a source, and
thereby unblocking the Spanish postal rung gated behind it — is served at the
draft boundary. The ladder-side consumption is a separate surface owned by the
lane authoring the counterparty-side selection; it was in flight in the same tree
and picked up both new draft fields directly.

Declaring `FREE_TEXT` rather than adding a form member follows the postal
precedent: the bounded registry vocabulary owns the matching, and a rule in the
grounder would be a second, weaker copy upstream of that authority.

Role evidence is structurally unavailable to these fields — it derives from the
tax-identifier form and the contract validator refuses the instruction on any
other form — so party attribution rests on the prose in each row's form
instruction plus the anchor. The instructions were written knowing that is the
only attribution available.

## Verification

Both lanes were run sequentially over the affected suites.

Unit lane:

    uv run --no-sync pytest -n0 -q -p no:randomly src/cadrumo/llm/tests
      src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py
      src/cadrumo/entrypoints/cli/tests/test_evidence_provenance_payload_parity.py
      -m "unit and not external_tool and not os_keychain and not resident_service"
    388 passed, 3 deselected in 77.89s (0:01:17)

Integration lane:

    uv run --no-sync pytest -n0 -q -p no:randomly <same paths>
      -m "integration and not external_tool and not os_keychain and not resident_service"
    2 passed, 389 deselected in 2.83s

Three mutations were applied from outside the repository at plugin module scope,
each printing a marker so a green run could not be misread as a sound gate. A
control run with the plugin loaded and no mutation selected passed 103 tests,
proving the harness itself is inert.

Dropping the grounded supplier country on the way out of the dispatch reddened
the grounder's declared-field round. Removing both country rows from the contract
declaration reddened forty tests including both parity directions. Removing the
customer country from the projection schema reddened the extract envelope's
whole-envelope carry, which is the surface where an unmirrored draft field raises
for every document.

## Notes

A gate committed at the time the work began asserted that no draft field carried
a country, pinning the exact gap this Step closes. It was a test encoding the
current defect as the contract, so it had to be corrected rather than worked
around. The lane owning the establishment ladder rewrote it in the same tree,
narrowing the claim to the structured parsers, which remain a separate Step's
scope.

The anchor-not-equal gate iterates a hardcoded tuple of monetary field names, so
the two country anchors are outside its coverage. They honour the non-equality
property by author convention only, which is the same position the postal anchors
are in and is already rowed separately.

The structured reading path was deliberately left out of scope: its country
source is a separate Step, and the parsers were not touched.
