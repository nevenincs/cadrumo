---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a797f4c2d8aee143b4a9233620135bfe7cd8cc9cf228492d1fed3d9a449ceb71'
step_id: 'S10'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Surface the provenance envelopes on every operator-facing extract and confirm JSON payload at parity with casilla grounding, gated by the JSON schema conformance suite

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

**This record was reconstructed by audit from evidence at HEAD. It was not authored
by whoever implemented the Step.** The payload fields, their production population
sites and the gate module all landed inside anonymous sweep commits with no exec
record and the plan row stayed open; a later audit read the production sites, re-ran
the gate and wrote this.

- Add `EvidenceFieldProvenancePayload` and carry `provenance` and `discrepancies` on
  both `EvidenceExtractResult` and `EvidenceConfirmResult` in
  `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`.
- Populate them on the production extract path by spreading the draft's JSON dump
  under the operator-reference fields, and on the production confirm path by reading
  the envelopes off the pre-override draft the confirmation was based on.
- Carry a `provenance_fields` count on the text surface, which cannot render a
  per-field envelope legibly, while the JSON payload carries the envelopes whole.
- Gate both surfaces with
  `src/cadrumo/entrypoints/cli/tests/test_evidence_provenance_payload_parity.py`.

## Outcome

Provenance now reaches the operator at parity with casilla grounding, on BOTH evidence
surfaces. Extract alone would not have been enough: confirm is the surface an operator
meets when a record is actually minted, and provenance present at review but absent at
confirm is missing exactly where it is least affordable.

Both schemas are registered under their command paths in the shared schema registry,
so the JSON schema conformance suite the Step names as its gate sees them. A
property-based case additionally walks the full nested schema document, `$defs`
included, and fails on any property name reading as a self-reported model confidence —
gated on the property rather than on a field list, so a future field fails whatever it
is called.

**Named honestly, as a residual rather than a defect:** the gate asserts the
SERIALIZED envelope body of both schemas, and the production population sites were
confirmed by reading `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`, but no test
drives either CLI command end to end and asserts the emitted envelope carries the
provenance. The Step's stated gate is the schema conformance suite, which is
schema-level by construction, so this is the row delivered as written; an end-to-end
assertion would be a strengthening, not a correction.

Introducing commit for the gate module, established by first-add archaeology:
`4a941f78fc`.

## Verification

Run at audit time against HEAD, sequential, cache disabled. Both lanes were run,
because the parity module is unit-marked while the conformance suite the Step names as
its gate is integration-marked — a unit-lane-only run would have silently deselected
the named gate and still read green.

Default marker lane (`unit and not external_tool and not os_keychain`):

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_aeat_record_projection.py src/cadrumo/entrypoints/cli/tests/test_evidence_provenance_payload_parity.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -p no:cacheprovider -q
    12 passed, 185 deselected in 1.68s

Integration lane, which is where the named conformance gate actually executes:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_aeat_record_projection.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -p no:cacheprovider -m integration -q
    163 passed, 6 deselected in 29.39s

The gate module is `test_evidence_provenance_payload_parity.py`. Its parametrised
`test_both_evidence_surfaces_declare_the_provenance_channel` asserts registration and
the channel on both commands;
`test_the_extract_envelope_body_carries_every_envelope_whole` and
`test_the_confirm_envelope_body_carries_the_drafts_provenance` assert the serialized
body keeps origin, grounding outcome, anchor and candidates; and
`test_no_operator_surface_carries_a_numeric_model_confidence` holds the permanent
ruling against a self-reported score.

## Notes

The residual named in the Outcome — no end-to-end CLI assertion over the emitted
envelope — is stated there rather than here because it qualifies the delivery, not an
incident during it.
