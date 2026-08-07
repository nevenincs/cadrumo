---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:13c86b200a17f2da9397b9e9b0bbaa8ce1b956eb80a8cc3ca48df4598a412006'
step_id: 'S120'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Carry the party postal address through the read path, since no address or postal field exists anywhere on it today and the deterministic evidence separating the three Spanish IVA territories is the postal code, whose first two digits are province-coded. This is the same atomic contract widening the regime legend needed and must land as one change across the field contract, the response schema, the anchor mirror, the grounding dispatch, the draft, the projection payload and the fully-populated fixtures, or it reds the parity gates for every lane. Reject the IVA-rate shortcut: a rate evidences where the SUPPLY is located, not where the PARTY is established, and those are different questions, so using it would give a confident wrong answer on the axis where a wrong establishment silently converts an intra-community operation into a domestic one

## Scope

- `src/cadrumo/domain/iva`
- `src/cadrumo/application/ledger`

## Description

- Declare `supplier_postal_code` and `customer_postal_code` in the one invoice
  field contract, each adjacent to the identifier of the party it belongs to.
- Mirror both on the transcribed-value schema and on the anchor schema.
- Ground both through the declared-form dispatch and carry them into the draft
  with a provenance envelope each.
- Add both to the draft and to the operator extract payload.
- Populate both, off-default and party-distinct, in the three fully-populated
  fixtures.

## Outcome

Two fields, not one. The row says "the party postal address"; the classifier
gap it serves names `issuer_residency` **and** `customer_residency`, and one
shared code cannot express an issuer in Las Palmas billing a customer in
Madrid. Landing one now would have forced a second contract widening later,
which is exactly the atomicity the row exists to avoid.

The declared form is the existing free-text form rather than a new postal form.
The territorial reading is already owned by
`territorial_scope_for_spanish_postal_code`, which refuses anything that is not
five digits and refuses it to nothing rather than to the peninsula. A
length-or-digit rule in the grounder would have been a second, weaker copy of
that judgment sitting upstream of it.

The address country field was not added, per the standing ruling: an address
country is printed as a name in the document's own language, so asking a reader
for a two-letter code is a translation, and the transcribed tax-identifier
prefix already carries the country.

## Verification

Focused parity and fixture gates, re-run against the moved tree after the change
landed:

    uv run --no-sync pytest -n0 -q src/cadrumo/llm/tests/test_invoice_field_contract.py src/cadrumo/llm/tests/test_invoice_field_anchors.py src/cadrumo/llm/tests/test_invoice_role_evidence.py src/cadrumo/llm/tests/test_regime_legend_vocabulary.py src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py src/cadrumo/application/ledger/tests/test_draft_projection_parity.py src/cadrumo/entrypoints/cli/tests/test_evidence_provenance_payload_parity.py
    142 passed in 79.04s (0:01:19)

The three scoped packages, sequentially, under the configured default marker
expression `unit and not external_tool and not os_keychain`:

    uv run --no-sync pytest -n0 -q src/cadrumo/llm src/cadrumo/application/ledger src/cadrumo/entrypoints/cli/tests
    2 failed, 1965 passed, 2967 deselected, 15 warnings in 493.62s (0:08:13)

Both failures are outside this surface. One is a live-CLI module exceeding its
own size budget in a file this change never opens; the other is the registry
loader refusing mid-run with "registry directory changed during cache
fingerprinting; retry after concurrent registry writes settle", a concurrent
write by another lane rather than a regression.

Three mutations, each installed from outside the repository at plugin module
scope so the patch lands before the modules under test are imported. Each
plugin asserts its own target is present and prints an activation line, so a
fully-green run would have been read as a patch that never landed rather than
as a sound gate.

Deleting the two rows from the contract declaration:

    PYTHONPATH=<outside> uv run --no-sync pytest -n0 -q -p mutate_m1 <focused paths>
    M1 ACTIVE: contracts 14 -> 12
    40 failed, 46 passed in 98.69s (0:01:38)

Making the grounder drop every postal code while grounding everything else:

    PYTHONPATH=<outside> uv run --no-sync pytest -n0 -q -p mutate_m2 <focused paths>
    M2 ACTIVE: _ground_text drops every *_postal_code
    2 failed, 84 passed in 107.29s (0:01:47)

Rebuilding the operator payload without the two fields, which is the projection
trap the regime legend hit once:

    PYTHONPATH=<outside> uv run --no-sync pytest -n0 -q -p mutate_m3 <projection paths>
    M3 ACTIVE: payload rebuilt without the postal fields
    4 failed, 6 passed in 1.96s

The projection parity gate stays green under M2 legitimately: it builds its
draft by hand and the grounding stage is not on its path. Symmetrically, the
grounding gates stay green under M3.

## Notes

The change reached HEAD inside another lane's whole-tree sweep commit rather
than under a pathspec commit of this lane's own. All seven files landed in that
one commit, so the contract widening is unsplit and no parity gate ever saw a
partial state. This lane could not have committed at the time regardless: the
repository index was held by another process, and the hold was reported rather
than cleared.

The structured e-invoice reading path leaves both fields absent. Its parser
exposes no address, so wiring it needs a change in the inbound e-invoice
adapter, outside this row's scope. This is the same shape the regime legend
carried before its own structured-path wiring landed separately.
