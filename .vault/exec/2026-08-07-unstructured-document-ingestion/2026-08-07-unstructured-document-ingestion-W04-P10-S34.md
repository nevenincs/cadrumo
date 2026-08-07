---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:99ed188bd3213a256a277ab8dc3d27394059f7662df7f29f852f1c5f6abd972d'
step_id: 'S34'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Build the harness runner pinned to key sha256 e2db6a49, recording model identity, revision and engine route on every result, stamping the corpus GAPS section-1 optimism caveat on every Spanish figure, and resolving twin pairs from the prose notes field until the corpus grows a structured link

## Scope

- `dev`

## Description

- Add the harness package under `dev`, holding the pinned key reader, the result taxonomy, the caveat surface, the recorded reference points and the runner.
- Pin the corpus key by content hash and byte length, refusing any other key BEFORE the payload is parsed, so an unpinned key reaches no derivation.
- Re-derive every denominator from the key itself: totals by provenance class, stage-1 reference texts, twin pairs, vision-path documents and the category-scorable set.
- Record model identity, revision and engine route as required fields on every result row, with the route a closed set distinguishing gated cloud, local on-host and deterministic.
- Stamp the optimism-bias caveat automatically on every Spanish document's row, derived from the document's own language axis rather than supplied by the caller.
- Resolve twin pairs by matching the prose notes sentence, verify each resolved original exists, and print the prose dependency in the report header.
- Compare amounts in exact decimal against the key's own cent tolerance, and print a sanity line contrasting the decimal and binary-float answers.
- Add the gate: 23 unit-lane contract tests and 12 corpus-anchored tests.

## Outcome

Every denominator was re-derived from the key before anything was written down, and the widely-circulated stale figures are wrong in the direction that matters. The measured breakdown is 302 documents as 30 generated, 66 acquired-real and 206 operator; 48 stage-1 reference texts; 7 twin pairs; 130 vision-path documents; 59 category-scorable. Provenance class is derived from markers exclusive to each class and then cross-checked against the path prefix, because two independent derivations that agree are evidence where one is an assumption; a disagreement raises rather than reclassifying documents underneath a published breakdown.

Two derivations that a natural filter gets wrong are encoded rather than described. The generated documents carry NO scorability flag at all, because their category is intrinsic, so the scorable set is a union of the explicitly-flagged entries and the generated ones: reading the flag alone yields 29 where the answer is 59, and both numbers are plausible enough to survive review. Separately, a null truth value marks a field the document LACKS, so it is a fabrication trap rather than a scorable slot; the corpus carries 1,364 such slots.

The runner deliberately measures nothing. It accepts rows from a caller that drove real product entry points, so no reader, prompt, rasteriser or transport is reimplemented here — a shadow parser measures itself, and one was deleted from an earlier harness for exactly that. Keeping the engine outside also means the runner needs no import of a product private module, which is not merely stylistic today: see the reachability finding in the Notes.

The key's internal schema version is loaded but printed only as a labelled do-not-cite. It reads "1.0" and has never tracked the key through its revisions, so it identifies nothing; printing it labelled is better than omitting it and letting a reader find it unaided. The header prints the content hash before any figure, and a test asserts the hash precedes the first row in the rendered output, so there is no rendering path that emits a number before the key it was measured against.

The twin link is a sentence, not a relation. The harness resolves it, verifies every resolved original exists so a mistyped reference raises instead of yielding a dangling pair, and states in the report that the link is prose and will break silently if the corpus rewords it. A twin-delta figure is therefore always read beside the pair count it was computed over.

## Verification

    uv run --no-sync python -m pytest dev/ingest_harness/tests -q -p no:randomly -n0 --collect-only
    23/35 tests collected (12 deselected) in 0.11s

    uv run --no-sync python -m pytest dev/ingest_harness/tests -q -p no:randomly -n0
    23 passed, 12 deselected in 0.26s

    uv run --no-sync python -m pytest dev/ingest_harness/tests -q -p no:randomly -n0 -m integration --collect-only
    12/35 tests collected (23 deselected) in 0.11s

    uv run --no-sync python -m pytest dev/ingest_harness/tests -q -p no:randomly -n0 -m integration
    12 passed, 23 deselected in 0.47s

Thirty-five tests across two lanes, all counts read back from log files on disk. The split is deliberate: the refusal contracts run against a small synthetic key payload so they execute anywhere, and only the facts about the real corpus carry the integration marker, because that corpus is external and in-repo CI does not have it. That is a lane rather than a skip — the corpus-anchored assertions run wherever the corpus exists and fail honestly if it is present but changed.

    uv run --no-sync ruff check dev/ingest_harness/
    All checks passed!

The type checker reports zero findings for this package.

Four mutation proofs cover this Step, each driven from a throwaway plugin on the interpreter path outside the repository, so nothing under the repository was edited and a crashed run could leave no residue.

Dropping the no-authored-truth check reds exactly one test.

Disabling caveat stamping reds exactly one test, the Spanish stamping assertion.

Reading the scorability flag alone, without the generated union, reds two corpus-anchored tests and reports 29 against the expected 59.

Removing the key pin so an arbitrary key is accepted reds exactly one test, the pin refusal.

    uv run --no-sync python -m pytest dev/tests dev/ingest_harness -q -p no:randomly -n0
    6 failed, 212 passed, 14 deselected in 82.35s (0:01:22)

All six failures are peer-owned and were recorded rather than patched; none names this package. Five are registry-conformance progress-ratchet failures from a peer's locale sweep, which dropped translated labels from 25,767 to 25,732, and one is an import-hygiene shim-module test.

## Notes

**Reachability finding, reported rather than worked around.** The deterministic stage-1 producers and the evidence resolver are NOT on the ledger package's public facade; only the data types are. A harness driving the real deterministic stage-1 entry point therefore cannot reach it without importing a private module, which the architecture forbids. This package does not clone those surfaces and does not reach into the private module — the runner takes rows from an injected engine instead. Promoting those four symbols is a precondition of the measurement Steps that consume this instrument, not of this one.

A prior harness beside the corpus carries copies of product surfaces. It was read as prior art and deliberately neither extended, depended upon, nor deleted.

The package was committed by a peer sweep before this lane could commit it. The working tree was confirmed byte-identical to the committed content across all nine files, so nothing was lost and no commit was issued from this Step.

The corpus tree is external, read-only and not a git repository. Nothing in this package opens it for writing, and every read in this Step was a read.
