---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a93df26021436477528c93b7a699fcb090434231c6eb31f11defe7bee2e5b8f1'
step_id: 'S61'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Derive per-item idempotency keys from content address plus direction riding the evidence idempotency guard so a re-run reports no-op rows

## Scope

- `src/cadrumo/application/ledger`

## Description

- Derive an item's identity from its content address and its declared direction,
  and from nothing else.
- Carry per-item outcomes as typed rows, with a refusal tied to the reason that
  justifies it in both directions.
- Report a run's failure as "any item failed", never "the first item failed".

## Outcome

Identity is the document's bytes plus the direction declared for them. No clock,
no filename, no run identifier — each of those differs between two runs over the
same document and would turn an idempotent re-run into a duplicate write.

Because the key is **derived rather than stored**, resume after a crash is
simply re-run: there is no journal format to invent and no progress file to
leave on disk. The completed-item record is the state.

Direction is part of the key rather than an attribute beside it. The same bytes
filed as issued and as received are two genuinely different records — a sale and
a purchase — and an address-only key would collapse them, silently dropping one.
The test for stability and the test for that distinction are deliberately
paired: a key stable enough to be idempotent must still not over-collapse, and
proving only the first would pass equally for a constant.

Per-item rows carry four outcomes. `no_op` is a success — already ingested under
this identity, neither re-read nor re-written. `pending_review` is neither
success nor failure: a document correctly routed to a human has not failed, so
it does not set the run's failure flag, while still appearing in the summary. A
refused row must carry its reason, and a reason may not appear under any other
status; either way round the rows and the summary would disagree about what
happened.

The summary names every status even at zero, because a status missing from a
report reads as "not applicable" rather than "none occurred", and those are
different claims to an operator deciding whether to look further.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_batch_ingest.py -p no:randomly -n0
    12 tests collected in 0.11s
    12 passed in 0.22s

Three mutations bearing on this Step, applied from a throwaway plugin outside
the repository so no tracked file changed:

| mutation | reddened |
| --- | --- |
| fold a clock into the identity | **1** |
| drop the direction from the identity | **1** |
| abort the run at the first refusal | **2** |
| make an item awaiting review fail the run | **1** |

The abort mutation reproduces the shape the adjacent statement-import folder
path still had at the time — a bare comprehension with no per-item guard — which
is what makes it worth proving rather than assuming.

## Notes

The identity function is deliberately not a hash of its inputs. A readable
`direction:address` string is greppable in a report and in storage, and the
inputs are already a digest and a closed enum, so hashing them again would buy
nothing and cost every operator who has to match a row against a file.

This Step delivered the identity and result primitives. The runner that consumes
them — walking a directory and executing the pipeline per item — is a concurrent
lane's work in the same module, and is not covered here.
