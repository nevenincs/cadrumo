---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:284a4a42771e959a32e7e46b356ed0d6c960266a94fd76b199354841ddb97bed'
step_id: 'S65'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Persist any batch state through secure storage only, with no spool, journal or progress file, gated by the sensitive-persistence gate scan and an anti-tautology proof

## Scope

- `src/cadrumo/application/ledger`

## Description

- Build the runner the ordering and identity primitives were written for: walk
  the sources, execute the pipeline per item, return typed rows.
- Hash each source in memory and release it, re-reading at work time rather than
  holding a folder of documents at once.
- Route the only two writes through secure storage: the encrypted evidence
  record and the encrypted draft.
- Gate it with a whole-tree before/after comparison plus a plaintext search
  carrying its own positive control.

## Outcome

The runner has no batch state of its own, which is the strongest available form
of the Step's requirement: there is nothing to write to a spool because there is
nothing to persist between items. Resume is re-run, and what makes that true is
that the store's own idempotent record IS the state.

**Completion is evidence AND draft, not evidence alone.** This is the part that
was nearly wrong. The evidence store's guarded no-op returns an empty event
tuple, and reading that alone as "already done" is the obvious implementation.
It is also a trap: a document whose bytes attach fine but whose READ fails — a
malformed PDF, or a transient absence of an on-host reader — leaves exactly that
state behind. Treating it as complete would report that document as an untroubled
no-op on every later run and never attempt it again. The document would be
silently stranded, and the row would say nothing was wrong. So an item counts as
complete only when its draft is present too, and a previously-unreadable
document stays a visible refusal on every re-run until it is fixed.

The bytes are read to hash and released, then re-read at work time. Holding a
whole folder in memory is unbounded, and the alternative to holding them is
spilling them — which is the spool this design exists without.

A source that cannot be read at all is reported in its own channel rather than
as an item. An item's identity IS its content address, and a file with no
readable bytes has none to derive one from; a placeholder would put a fabricated
value into the field that both ordering and idempotency key on, and a second
unreadable file would then collide with the first. It still reaches the operator
and still fails the run.

## Verification

The unit-lane primitives this runner is built on, at HEAD:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_batch_ingest.py -m unit -p no:randomly
    12 passed in 5.92s

Twelve collected, twelve ran, none deselected.

The runner's own integration lane, twelve tests including both no-spool proofs:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_batch_ingest_runner.py -m integration -p no:randomly
    12 passed in 22.44s

The default marker expression is worth recording, because the first run of this
file selected **nothing**: the lane is `unit` by default and these tests are
`integration`. The runner printed `NOTHING RAN` with an explicit warning that a
green result meant the selection matched nothing. Had that banner not existed,
an exit code of 5 could have been read as a pass.

Three mutations were applied from a throwaway plugin outside the repository, so
no tracked file changed and a peer sweep could not commit one. Each reddened
exactly its intended test and nothing else:

    keep_enumeration_order        -> 2 failed, 10 passed
    identity_folds_a_clock        -> 1 failed, 11 passed
    identity_drops_the_direction  -> 1 failed, 11 passed

The first reddens both the row-ordering and the source-ordering tests; the
second and third are the paired stability and non-collapse properties of the
identity key.

The three that matter most for THIS Step target the integration lane, with their
blast radii recorded rather than summarised as "it failed":

    abort_on_first_failure  -> 9 failed, 3 passed
    rerun_double_writes     -> 1 failed, 11 passed
    spool_to_disk           -> 3 failed, 9 passed

The wide first radius is the finding, not noise: letting one item's failure
escape destroys the run, so nearly every property collapses at once — which is
exactly the cost the design exists to avoid. The second is surgical, reddening
only the idempotency gate. The third reddens both no-spool proofs and, honestly,
the idempotency gate too: a spool file written beside the inputs becomes a batch
input on the next run, so a spool does not merely leak, it corrupts the item set.

## Notes

The byte-identical assertion is worth recording as a defect this Step authored
and caught. It was written while the tree was uncollectable, committed unrun
with that status stated, and was **wrong**: it compared run two against run one,
and those legitimately differ, because the item run one ingested is a no-op by
run two. The gate asserted the design was broken. Running it was what found
that; reasoning about it had not. Runs two and three are the pair that must be
identical, and the corrected form is now mutation-proven rather than argued.

The tree was uncollectable for roughly seven minutes in the middle of this work:
an uncommitted peer change declared `LLMConsentError` with no ErrorCode registry
entry, so `bind_error_code` raised on every import of `cadrumo.llm`, which
`_extraction_draft_store` pulls in transitively. It cleared on its own and the
lane was re-run in full afterwards; nothing here rests on a pre-break result.

Three mutation results were **voided and re-run**. The mutation plugin was
written to the shared scratchpad under a generic name, and a concurrent
teammate's script overwrote it mid-flight, so those three runs exercised
someone else's file and exited non-zero for an unrelated reason. A non-zero exit
from a mutation run reads as success — the gate reddened — which is precisely
why that was worth catching rather than accepting. The plugin was renamed to a
lane-specific name and every mutation above re-run.

No model was loaded, pulled, or contacted. The corpus documents used are the
bundled synthetic fixtures, and the deterministic structured-record reader is a
parser. One outbound connection attempt to the local runtime appears in the logs
as a refused connection while the malformed PDF falls through to the vision
route; it fails closed and becomes that item's refusal row, which is the
designed behaviour.

The consent gate is not yet built, and this runner does not route around it: no
per-item call site was invented for a gate that does not exist, and nothing here
acquires consent once for a run.

S63, the batch-wide inference pacing, is **not started** and is not covered by
this record. The admission primitive has no production caller anywhere yet, and
the routing decision that would say which items are inference-bearing lives
inside the extractor. Pacing therefore needs either a duplicate of that routing
— the fragmentation the discovery mandate exists to prevent — or a seam
extracted from it, and a concurrent lane was actively rewriting that same
reading chain. Deferred rather than half-built.
