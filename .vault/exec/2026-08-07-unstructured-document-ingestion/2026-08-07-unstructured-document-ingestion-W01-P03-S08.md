---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1d06f87b11802c5faae4c150bb773ce2317a561128c690f984674097b0ebf986'
step_id: 'S08'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add the projection-parity gate asserting every draft field survives to the confirm-surface payload, proven by mutation: drop one field from the projection and observe red and ## Scope

- `src/cadrumo/application/ledger/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the projection-parity gate asserting every draft field survives to the confirm-surface payload, proven by mutation: drop one field from the projection and observe red

## Scope

- `src/cadrumo/application/ledger/tests`

## Description

**This record was reconstructed by audit from evidence at HEAD. It was not authored
by whoever implemented the Step.** The gate landed inside an anonymous sweep commit
with no exec record and the plan row stayed open. The mutation proof below, however,
was RUN at audit time rather than reconstructed: the Step's own acceptance condition
is an observed red, and a record asserting one nobody watched would be exactly the
defect this campaign keeps finding.

- Add `src/cadrumo/application/ledger/tests/test_draft_projection_parity.py`, gating
  parity between the application-layer `InvoiceDraft` and the CLI-layer
  `EvidenceExtractResult` payload the operator actually receives.
- Assert structural parity in both directions: no draft field may lack a home on the
  payload, and no payload field may lack a draft origin outside a named frozenset of
  three operator-reference fields.
- Assert value survival for every field at once, building the payload exactly the way
  the CLI builds it (the draft's JSON dump spread under the reference fields) rather
  than re-implementing the projection.
- Assert the provenance envelopes arrive whole, keeping origin, grounding outcome,
  anchor and ambiguity candidates.

## Outcome

The gate sits on the PROJECTION rather than on the reader, which is where the
measured defect was: values recovered correctly and then discarded between the draft
and the payload. It gates on the property (every draft field reaches the payload,
carrying its value) rather than on a field tally, so it does not encode today's shape
and then detect nothing.

The projection the gate reproduces is the real one. The production extract command in
`src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py` builds its payload as the three
reference fields spread with `draft.model_dump(mode="json")`; the gate builds the same
shape. A field dropped from the payload model therefore breaks production the same way
it breaks the gate.

Introducing commit, established by first-add archaeology: `4a941f78fc`.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

Green at HEAD, sequential, cache disabled, default marker lane
(`unit and not external_tool and not os_keychain`):

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py src/cadrumo/application/ledger/tests/test_draft_projection_parity.py -n0 -p no:cacheprovider -q
    15 passed in 1.88s

**The mutation, run at audit time.** Applied from OUTSIDE the repository as a pytest
plugin held in a scratch directory and injected on `PYTHONPATH`, so no tracked file
changed and no peer sweep could commit it. The plugin deletes `suplidos_amount` from
`EvidenceExtractResult.model_fields` at `pytest_configure`, before the gate module
imports the class, and rebuilds the model:

    PYTHONPATH=<scratch> uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_draft_projection_parity.py -n0 -p no:cacheprovider -p audit_w01p03_s08_drop_field_plugin -q
    [audit-mutation] dropped 'suplidos_amount': 27 -> 26 fields
    3 failed, 1 passed in 1.11s

The plugin's own banner is the proof the mutation LANDED rather than silently
no-opping; a fully green run would have been the tell that it never reached the class
under test.

**Where the red came from.** The primary red is the gate's own structural assertion,
`test_every_draft_field_exists_on_the_extract_payload`, failing on a plain
`assert not missing` with the message "the extract payload drops these draft fields
entirely: ['suplidos_amount']". That is the gate speaking, not fixture setup and not
an unrelated production guard. Two further tests,
`test_every_populated_draft_value_survives_into_the_payload` and
`test_the_provenance_envelopes_arrive_whole`, red on a pydantic `extra_forbidden`
`ValidationError` raised by the payload model as the gate exercises the projection —
also the gate binding, by a different mechanism. The fourth test,
`test_the_payload_adds_nothing_beyond_the_declared_reference_fields`, correctly stays
green: it watches the opposite direction, and this mutation removed rather than added.

The mutation is reachable only because the fixture populates `suplidos_amount`
off-default, which the S06 fixture gate guarantees. The structural assertion is
stronger still: it compares field sets and is independent of any fixture.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The parity gate reaches from the application package into `entrypoints.cli`
deliberately, and says so in its module docstring: the parity being asserted is
precisely between those two ends, and a gate that could see only one could not assert
it.

Adjacent and NOT covered by this gate: the `EvidenceConfirmResult` payload carries
provenance and discrepancies but is not enrolled in the whole-field parity check,
because it projects a minted catalogue invoice rather than the draft. Its coverage is
the separate provenance-parity module recorded under S10.
