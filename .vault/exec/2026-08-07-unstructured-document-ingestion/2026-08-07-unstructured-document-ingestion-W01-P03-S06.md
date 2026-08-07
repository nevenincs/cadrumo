---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a564466bd9940da63acf8bc7ffd885bc63b87b6e8832ef19119c61604a792e6a'
step_id: 'S06'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add the per-field provenance envelope (FieldOrigin, verbatim anchor, grounding outcome, ambiguity candidates) to the draft model family, gated by a strict roundtrip with every defaultable field populated non-default

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

**This record was reconstructed by audit from evidence at HEAD. It was not authored
by whoever implemented the Step.** The work landed inside anonymous sweep commits
with no exec record, and the plan row stayed open; a later audit established what
was true, re-ran the gate, and wrote this. Every claim below rests on code and test
output read at audit time, not on an implementer's report.

- Add `FieldOrigin` and `FieldGroundingOutcome` as closed core taxonomies in
  `src/cadrumo/core/_field_origin.py` and `src/cadrumo/core/_field_grounding.py`.
- Add `FieldProvenance` and `FieldAmbiguityCandidate` to the draft model family in
  `src/cadrumo/application/ledger/_evidence_draft.py`, carrying origin, verbatim
  anchor, grounding outcome, competing ambiguity candidates and a free-text note.
- Validate the envelope against the draft's own fields rather than a hand-listed
  enum, and refuse an anchored field with no anchor, an ambiguous field with fewer
  than two candidates, candidates recorded under a decided outcome, an envelope
  naming a field the draft lacks, and two envelopes for one field.
- Gate the family with a strict JSON round trip over a fixture that populates every
  defaultable field off-default, plus a fixture gate and an anti-tautology proof.

## Outcome

The per-field envelope is on the draft family and carries all four axes the Step
names. Provenance is per FIELD rather than per document, so an exactly-read value
stays distinguishable from a model-read one. The family carries no numeric
confidence axis, and a property-based gate (not a field tally) keeps it that way.

The Step's gate condition is met in full, not narrowly: the round-trip fixture is
itself gated by `test_every_defaultable_field_is_populated_off_default`, which
compares the fixture against a bare draft and fails if any defaultable field is
left at its default. Without that, the round trip would be vacuous on exactly the
save-drops-field regression it exists to catch.

Introducing commits, established by first-add archaeology rather than by report:
`0c98b01052` for the core taxonomies, `4a941f78fc` for the draft-family models and
their gate module.

## Verification

Run at audit time against HEAD, sequential, cache disabled, default marker lane
(`unit and not external_tool and not os_keychain`):

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py src/cadrumo/application/ledger/tests/test_draft_projection_parity.py -n0 -p no:cacheprovider -q
    15 passed in 1.88s

The gate module is `test_evidence_draft_provenance.py`. The assertions that carry
this Step are `test_every_defaultable_field_is_populated_off_default` (the fixture
gate), `test_populated_draft_survives_a_real_json_round_trip` (strict equality
across a real JSON-text cycle), and
`test_a_dropped_field_is_surfaced_rather_than_re_defaulted` (the anti-tautology
proof: delete a defaultable field from the serialized payload, require the reload
to differ from the original). The five refusal cases covering the envelope's
self-consistency invariants are in the same module.

## Notes

A sibling module in the same package, `test_evidence_draft.py`, fails collection at
audit time on a missing `_parse_labelled_amount` import. That is another lane's
in-flight work, unrelated to this Step, and was excluded from the runs above rather
than touched.
