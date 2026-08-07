---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a90e86d0c4c11afd41923bf83b060f7d3795592395b16f1e0ec1546a17181c17'
step_id: 'S116'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Make the persisted draft extractor field carry transport truth rather than reader identity

## Scope

- `src/cadrumo/application/ledger`

## Description

- Record the transports that carried a document's reading beside the stored draft, separate from the reader label.
- Derive the batch path's value from the enforced consent refusal rather than from configuration, and name the constant for what it asserts.
- Classify artefacts in the withdrawal survey by those transports instead of by parsing the reader label.
- Gate it by driving the real batch path, plus the unknown case that path cannot reach.

## Outcome

The survey parsed the stored extractor label for a transport. The batch path stores a function name there, and does so deliberately: claiming one reader for a draft assembled from several would be the laundering the per-field provenance envelopes exist to prevent. That rationale is correct and was honoured rather than overridden. The consequence was that every batch-ingested draft parsed as unclassifiable and surfaced as cloud-derived — reproduced before the change and confirmed flipped after.

The resolution is that two different questions were sharing one field at the wrong granularity. Which reader produced a value is per-field and stays in the envelopes. Whether any bytes left the host is legitimately document-level, because if any field went off-host then the document did; the fact is monotone over fields and loses nothing by aggregation.

Empty means unknown and is surfaced, never read as on-host. The batch always records a transport, so that branch is unreachable from the batch path and is asserted directly.

The batch's own value is derived from an enforced refusal, not assumed: an evidence-derived request reaches an off-host provider only with a per-invocation consent token, the dispatch refuses without one, and this path mints and accepts none. The constant is named for what it asserts and carries the note that it must become a function of the token the moment this path gains one — which the peer work now wiring `off_host_provider` and `consent_token` into extraction will require.

## Verification

    uv run --no-sync pytest -n0 -p no:cacheprovider src/cadrumo/application/ledger/tests/test_consent_withdrawal.py -q
    18 passed in 5.31s

    uv run --no-sync pytest -n0 -p no:cacheprovider -m "" src/cadrumo/application/ledger/tests/test_batch_ingest_runner.py -k "surveys_as_on_host or records_the_transport" -q
    2 passed, 19 deselected in 9.82s

Three mutations, applied from a plugin outside the repository, with distinct blast radius:

    classify_by_the_extractor_label_again   2 failed  (batch survey gate + the unreadable-input case)
    treat_unknown_as_on_host                2 failed  (both unknown-must-surface cases, and correctly NOT the batch ones)
    batch_records_no_transport              2 failed  (both batch cases)

The second mutation was INERT on the first attempt and that was the useful result: the batch fixture always records a transport, so the unknown branch could not be reached from it. The gate was not weak; the corpus could not discriminate. Fixed by asserting the unknown case directly, after which the mutation bites.

The wider run shows thirteen failures across `application/ledger` and `llm`, none on this surface. Twelve trace to a required `settings` keyword a peer added to `_read_transcription_semantically` in their in-flight `_evidence_draft.py`; one is a live-network Anthropic test.

## Notes

The measurement in the report that opened this row was wrong in my favour and was corrected before work began. I had claimed the only production writer of the draft store was the re-derivation path; the batch path is a second writer and passes the function indirectly as `write_draft=`, so a grep for the call site never saw it. An indirect call through a parameter is invisible to the search that found the direct one.

The field was extended rather than renamed. The row's wording asks for the extractor field to carry transport truth, but the review lane's CLI displays that field as reader identity, and renaming it would have broken another lane's surface to express something a dedicated field expresses better. The batch rationale explicitly wants the label to stay a function name.

`_evidence_draft.py` carries heavy peer work and was excluded from every commit, as was `test_draft_projection_parity.py`.
