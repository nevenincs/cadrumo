---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a3d5766d563e71d8694401ca0d86ea5aec697999b1ff0f46623b11c9e264a6b2'
step_id: 'S11'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Produce the deterministic text-layer transcription into DocumentTranscription with reading order and printed forms preserved, gated by fixture tests asserting byte-faithful printed forms

## Scope

- `src/cadrumo/application/ledger`

## Description

- Split the existing on-host reader into `extract_evidence_pages`, returning one string per page with the media-kind guard, and reduce `extract_evidence_text` to a join over it, leaving both existing callers' signatures unchanged.
- Add `transcribe_text_layer`, projecting those pages into `DocumentTranscription` with the page count from the tuple length and the content address taken from the evidence record.
- Add `text_layer_transcriber_identity` and `TEXT_LAYER_TRANSCRIBER_NAME`, stamping origin `TEXT_LAYER` with the reader's name and its installed distribution version.
- Promote `DocumentTranscription` and `TranscriberIdentity` to the package facade through the existing lazy attribute map, its `__all__`, and its type-checking block.
- Add the acquisition fixture gate: 21 real-behaviour tests over reportlab-built multi-page PDFs.

## Outcome

Stage S1's deterministic half is delivered as a projection of the extraction that already existed, not a new extractor. Semantic discovery found the shared pdfplumber primitive and the in-memory evidence reader that already wraps it, so no extraction code was written.

No new module was created either. The on-host text-layer module already was the canonical home for this concept; a second module beside it would have been a parallel authority for one responsibility. The existing module was extended instead, which also meant no generated API stub had to be scaffolded and no peer stubs were swept.

The transcriber revision is read from the installed distribution rather than restated as a constant. A hand-maintained revision can lie the moment the dependency moves, and the dependency moving is exactly what changes the extracted text; read this way, an upgrade re-keys the transcription cache on its own.

Printed forms are preserved literally and the projection transforms nothing. The gate asserts against the source literals the fixture PDFs are authored from, never against the record's own output, because an output-versus-output equality still passes when both sides normalise identically. A negative direction asserts the machine-normalised forms never appear.

The facade promotion is a precondition of the vision-path step that consumes the record from another package, and it follows the lazy attribute pattern the package already uses. The vision path itself was not touched and remains held.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/ src/cadrumo/tests/test_import_hygiene_gate.py -n 0
    4 failed, 573 passed in 676.97s (0:11:16)

Collected 577, zero deselected. The new gate contributed 21 passed. All four failures are peer-owned and were recorded rather than patched: one untracked corpus fixture carrying no provenance declaration, and three import-hygiene failures from a private test reach that arrived in a peer commit without a matching entry in the test-debt ledger. Neither touches this step's surface.

    uv run --no-sync ruff check <touched files>
    All checks passed!

    uv run --no-sync --group typecheck basedpyright <touched files>
    0 errors, 0 warnings, 0 notes

Three mutation proofs, each driven from a throwaway plugin on the interpreter path outside the repository, so nothing under the source tree was edited and no residue could survive a crashed run.

Normalising the printed forms on the way into the record reds eight tests: the three source-literal assertions, the three normalised-form negatives, the cached-form assertion, and the within-page ordering assertion, which indexes lines that carry the printed forms and is therefore genuine collateral.

Reversing the page order reds exactly one test, the cross-page ordering assertion.

Stamping a vision origin with a false revision reds exactly two, the origin assertion and the name-and-revision assertion. The helper-agreement assertion stays green under that mutation by design, since both sides route through the mutated helper; it is a consistency check rather than an independent one, which is why the two independent assertions carry the proof.

Both refusal tests, for image evidence and for a PDF with no text layer, sit behind a positive control asserting the intact case transcribes through the same route first.

## Notes

A peer sweep committed all three touched files while the verification suite was still running. The working tree was confirmed identical to the committed content on every one of them before this record was written, so nothing was lost and no commit was issued from this step.

The package facade carried an unrelated peer edit reordering one existing export. A patch anchored to the committed revision and containing only additions was prepared so that edit could not be disturbed; the sweep landed both cleanly and the patch went unused.

The import-hygiene test-debt entry noted above will red every full-tree run until someone owns it. It predates this step.
