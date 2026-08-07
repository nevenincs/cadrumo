---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9a6c756069ae2e9193fc357461c04441ade513dab03e7a23da6f7c55819c29da'
step_id: 'S04'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the single typed DocumentTranscription record (reading-order text with printed forms preserved, page count, source content address, origin with model identity and revision) carrying the EvidenceInput serialization tripwires, gated by a strict roundtrip and tripwire refusal tests

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add `_document_transcription.py` holding `DocumentTranscription`: reading-order `text` (non-empty, excluded from repr), `page_count` at least one, the 64-character source content address, and a required `transcriber`.
- Add `TranscriberIdentity` carrying `origin`, `name` and `revision`, every one required with no default, and a `cache_key` property folding all three.
- Constrain the origin to `ACQUISITION_ORIGINS`, derived from the core `FieldOrigin` enum by comprehension rather than hand-listed.
- Carry the `EvidenceInput` serialization tripwires: `model_dump`, `model_dump_json`, iteration and pickling all refuse, and the refusal is registered as the model serializer so a parent embedding the record also raises.
- Add `TranscriptionCacheEntry`, the persistable mirror, with `to_cache_entry` and `to_transcription` as the single sanctioned durable route.
- Add the gate: 12 real-behaviour tests over tripwires, the strict roundtrip, printed-form fidelity, key composition and origin refusal.

## Outcome

The record's shape follows the governing decision literally: one typed record rather than a tagged union, because a text-layer read and a vision read differ in their transcriber and never in their type. A union would push a branch into every consumer for a distinction only provenance cares about, and would let a consumer forget the branch that matters.

The tripwires and the cache are in direct conflict, and resolving that was the substantive decision in this Step. The secure repository serializes a payload through `envelope.model_dump_json()` with no serializer context, so a nested refusal makes the record structurally unpersistable — the record cannot both refuse serialization and be cached unless there is a named escape. It is resolved as a pair: the in-memory record refuses every ordinary route, and `to_cache_entry` and `to_transcription` are the only way across, with an ordinary strict model on the far side whose sole writer is the encrypted repository.

That escape is a named method rather than a serializer-context flag deliberately. A context flag would make every durable site look like an ordinary dump and be invisible to a grep; a method name means every place a transcription becomes durable can be enumerated by searching for it. The cost is six duplicated field declarations, which is the price of the property.

The transcriber carries name and revision with no defaults on either half, and neither may be blank. The revision is load-bearing rather than decorative: a transcription produced under one prompt revision is not interchangeable with one produced under the next, so the revision is part of the cache key. A stamp that can be constructed without naming its producer is one that will eventually be constructed wrong, which is the failure a peer met on this campaign when a provenance stamp hardcoded a coarse label and would have claimed a cloud read was on-host.

Printed forms are preserved literally and nothing on the path transforms the text. The fidelity gate asserts against the source literal rather than against the record's own output, because an output-versus-output equality still passes when both sides normalise identically.

The accepted origin set is derived from the core enum's members rather than restated, so a new member cannot silently become an acquisition origin, and the refusal test parametrises over the set's complement rather than a hand-listed set.

## Verification

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/test_document_transcription.py src/cadrumo/application/ledger/tests/test_extracted_document_cache.py -p no:randomly -q --collect-only
    21 tests collected in 1.99s

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/test_document_transcription.py src/cadrumo/application/ledger/tests/test_extracted_document_cache.py -p no:randomly -q
    21 passed in 29.52s

Twenty-one collected, twenty-one passed, zero deselected; the counts were read back from the log files on disk rather than from terminal scrollback.

    uv run --no-sync ruff check <the four touched files>
    All checks passed!

    uv run --no-sync ruff format --check <the four touched files>
    4 files already formatted

The type checker reports zero findings for these modules; the four findings the full run carries are peer-owned and named in the Notes.

Two mutation proofs cover this Step, both driven from a throwaway plugin on the interpreter path outside the repository, so nothing under the source tree was edited and a crashed run could leave no residue.

Rebinding the record to a tripwire-free model carrying identical fields reds both tripwire tests, the direct one and the nested-parent one.

Widening the accepted origin set to the whole enum reds all three non-acquisition parametrisations. The widening is applied at collection finish rather than at configure, because the test parametrises over the set's complement and mutating it earlier empties the parameter list — the run would then go green on zero cases rather than on a working guard.

One earlier mutation attempt was invalid and was discarded rather than reported. Reassigning `model_dump` and `model_dump_json` to their base-class implementations left the registered model serializer refusing underneath, so the suite stayed green legitimately and the mutation proved nothing. It is recorded because the failure mode is easy to repeat: overriding a pydantic dump method does not remove a refusal registered as the model serializer.

A second invalid proof was caught in the tests themselves rather than in a mutation. Strict-mode pydantic refuses python-mode revalidation of `model_dump(mode="json")` output, so the first version of the unexpected-key refusal raised for the wrong reason and would have passed with the boundary broken. Every refusal assertion now runs the real JSON route and is preceded by a positive control asserting the intact payload loads through that same route.

## Notes

The record and its mirror were left off the package facade in this Step. The cross-package consumer is the vision-path Step in the inference package, and promotion is a precondition of that consuming change rather than of this one; the facade file was also the peer-owned surface of the preceding Phase. It was subsequently promoted by the text-layer acquisition Step, so nothing is outstanding.

The generated API stub scaffold is tree-wide and swept peer modules. Only this Step's own new stub and the ledger index entry were staged; nine untracked peer stubs and two peer stub deletions were left in the working tree for their owners and were not reverted. The staged index entry adds one line naming a peer module alongside this one, in a single hunk that cannot be split without hand-editing a generated file.

Four full-tree gate failures were recorded and deliberately not patched, none naming this Step's files: three import-hygiene failures from a peer's untracked test reaching a CLI private symbol with no matching test-debt entry, and one docstring anchor-link failure in an aggregation module.

One run surfaced an import error for a symbol mid-flight in a peer's domain package. It did not reproduce and every subsequent run was clean.
