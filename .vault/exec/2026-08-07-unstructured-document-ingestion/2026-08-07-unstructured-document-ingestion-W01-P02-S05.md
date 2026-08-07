---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9023684eb4421e50eb363afa549349c8de15b440e91342c74bce6f677f860400'
step_id: 'S05'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Wire the encrypted transcription cache through core secure storage keyed by source content address plus transcriber identity, gated by a real-adapter roundtrip, an on-disk mutation anti-tautology proof, and the sensitive-persistence gate scan reaching the new module

## Scope

- `src/cadrumo/application/ledger`

## Description

- Complete the existing extracted-document cache in place: its entry becomes the typed transcription mirror, replacing the bare string value and the non-key extractor field.
- Key every entry by `(source_content_sha256, TranscriberIdentity.cache_key)` rather than by content address alone, on both the write and the read side.
- Replace the accessors with `read_cached_transcription` and `write_cached_transcription`, returning and accepting the typed record.
- Keep the storage namespace, the repository class and the module home unchanged, so no adapter-side registry edit was needed.
- Add the gate: 9 real-adapter tests over the encrypted roundtrip, printed-form fidelity across the boundary, key composition, and the anti-tautology proof.

## Outcome

The cache was completed in place rather than duplicated, and that adjudication was the first question this Step had to settle. The governing decision names it directly, describing the transcription's cache as the extracted-document cache that the parent record authorises. Reading the module whole confirmed it: it had zero production consumers, stored a bare string, and carried the extractor as a non-key field. A second cache beside it would have been a parallel authority for one responsibility, so the existing one was finished instead. Because the namespace, repository and module name are unchanged, nothing in the persistence adapter package had to move and no peer-owned surface was touched.

The key gains the transcriber, and that is the behavioural change. Under the address-only key whichever reader ran last answered for every reader, which silently substitutes a probabilistic vision reading for a deterministic text-layer one. Under the composite key the two coexist, and a prompt-revision bump reads as a miss rather than a stale hit — so an improved reader re-reads instead of being served its predecessor's output forever. Replacement never crosses transcriber identities: one reader re-reading one document is the same fact re-derived, while a different reader is a different fact.

The anti-tautology proof was rebuilt after it was found to be passing for the wrong reason, and that is the most useful thing this Step recorded. Strict-mode pydantic refuses python-mode revalidation of `model_dump(mode="json")` output, so the original proof raised a validation error on the serialization mode rather than on the deleted field — it would have passed with the boundary completely broken. Both proofs now run the real JSON route the repository itself uses, every refusal is preceded by a positive control asserting the intact payload loads through that same route, and the deletion sweep covers five required fields including one nested inside the transcriber.

The persistence scan close-out distinguishes two things a zero result confuses. The census reports zero file-producing write sites in both modules, but zero is ambiguous between no writes and the scanner not seeing the module, so both were checked: the modules are present in the scan's production module set, and the detector was shown to fire on this module's own code shape.

## Verification

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/test_document_transcription.py src/cadrumo/application/ledger/tests/test_extracted_document_cache.py -p no:randomly -q --collect-only
    21 tests collected in 1.99s

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/test_document_transcription.py src/cadrumo/application/ledger/tests/test_extracted_document_cache.py -p no:randomly -q
    21 passed in 29.52s

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests -q
    535 passed in 332.94s (0:05:32)

Zero deselected on both selections; the counts were read back from the log files on disk. The roundtrips drive the real secure-object repository with a real key provider and a real SQLite engine, never a stand-in, and every defaultable field is populated non-default so a drops-field regression cannot hide behind a value that never differed.

Re-run against the later HEAD after a peer sweep landed on top: 21 passed in 8.74s, with the Step's six files showing no drift from what was committed.

Three mutation proofs cover this Step, each driven from a throwaway plugin on the interpreter path outside the repository.

Giving the persisted entry's text field a default reds exactly one test, the deletion proof, and nothing else. That is the anti-tautology proof biting precisely on the regression it exists to catch.

Making the sanctioned durable route drop the page count reds both strict-equality roundtrips, the unit one and the encrypted one.

Widening both the write and the read side to the address-only key reds exactly two tests, the two that assert key composition. An earlier version of this mutation was discarded as imprecise: it changed only the entry's key property, which broke read matching rather than widening it, so entries stopped matching at all and the miss assertion passed vacuously while four unrelated tests reddened. The corrected mutation widens both sides and produces the clean two-test signal.

The persistence scan close-out ran against the Step's own pinned commit rather than a moving name:

    uv run --no-sync python -m dev.write_site_census <the step's commit> --json
    site_count 95, scope production

Both modules appear in the scan's production module set, and both report zero file-producing write sites. The discriminating control parsed this Step's real source through the scanner's own detector, giving zero sites, then injected the exact forbidden violation into the sanctioned durable route — a path write and an open-for-write of the transcription text — and the detector returned two sites. The injection was done in memory against a string copy; nothing under the source tree was edited, and nothing was committed, which also matters because the census reads through a pinned revision and would not have seen a working-tree edit.

## Notes

The four full-tree gate failures recorded during this Phase are peer-owned and were not patched: three import-hygiene failures from a peer's untracked test reaching a CLI private symbol with no matching test-debt entry, and one docstring anchor-link failure in an aggregation module. None names this Step's files.

The generated API stub scaffold is tree-wide. Untracked peer stubs and peer stub deletions it surfaced were left in the working tree for their owners and were not reverted.

The regenerated feature index was left uncommitted deliberately. It carries wiki-links to execution records that are still untracked on disk, so committing it would publish links to documents that do not exist in the tree; it lands with them.
