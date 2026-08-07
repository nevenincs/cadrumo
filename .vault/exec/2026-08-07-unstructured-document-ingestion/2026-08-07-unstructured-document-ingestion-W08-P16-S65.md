---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a91dd98ed4d9ec593a5c27d68f736499ac2b692efc5a6f79698ee5cebd3959dd'
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

The runner's own integration lane, twelve tests including both no-spool proofs,
run immediately before the tree broke (see Notes):

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_batch_ingest_runner.py -m integration -p no:randomly
    12 passed in 22.06s

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

## Notes

**This Step is left open, and the reason is the mutation proof rather than the
code.** The three mutations above exercise the unit lane. The three that matter
most for THIS Step — abort-on-first-failure, a re-run that double-writes, and a
spool written to disk — target the integration lane, and that lane has been
uncollectable since shortly after its green run above. An uncommitted peer
change declares `LLMConsentError` with no ErrorCode registry entry, so
`bind_error_code` raises on every import of `cadrumo.llm`, which
`_extraction_draft_store` pulls in transitively. The plugin was rewritten to
import only the batch module, which does settle its own imports, but the test
file itself cannot be collected.

So the no-spool gate has run green and has **not** been proven to bite. A gate
that has never been seen to fail is worth much less than one that has, and this
is the Step where that distinction carries the weight. Marking it complete on an
unrun mutation proof would be exactly the "checked but not done" state the
campaign discipline exists to prevent.

One assertion in the integration file — comparing re-run rows byte-identically
rather than by content address — was written after the break and has never been
executed. It was committed rather than left in the working tree, with its unrun
status stated in the commit message, because an untracked or uncommitted change
in this tree is both invisible to discovery and liable to be swept into an
unrelated commit; recording it honestly was preferable to either.

No model was loaded, pulled, or contacted. The corpus documents used are the
bundled synthetic fixtures, and the deterministic structured-record reader is a
parser. One outbound connection attempt to the local runtime appears in the logs
as a refused connection while the malformed PDF falls through to the vision
route; it fails closed and becomes that item's refusal row, which is the
designed behaviour.

The consent gate is not yet built, and this runner does not route around it: no
per-item call site was invented for a gate that does not exist, and nothing here
acquires consent once for a run.
