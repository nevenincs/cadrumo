---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e4a6ed4063ef33ea7637c2c0c728130737fb1d9ea6a3f782e70926d8ecb58e54'
step_id: 'S62'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Order batch items deterministically by content address, gated by shuffled input directories producing identical reports

## Scope

- `src/cadrumo/application/ledger`

## Description

- Order finished rows by content address, with direction breaking the only tie
  that can arise.
- Order the SOURCES the same way, before any work happens.
- Gate both on every permutation of an input set, not a sample of them.

## Outcome

Two runs over the same documents report in the same order however the filesystem
enumerated them. A report whose row order depended on directory iteration could
not be diffed against the previous run, which is the first thing an operator
does after a partial batch.

Ordering is applied **before any work happens**, not only to the finished rows.
That is the part worth stating: ordering the output alone still leaves the
PROCESSING order dependent on enumeration, so which items an interrupted run
completed varies between runs — and both runs would report in a tidy sorted
order that looks deterministic while having done different work. Sorting the
sources closes that, and it is cheap.

Direction breaks a tie, which can only occur when the same bytes were submitted
under both directions in one run.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_batch_ingest.py -p no:randomly -n0
    12 tests collected in 0.11s
    12 passed in 0.22s

Two mutations, applied from a throwaway plugin outside the repository so no
tracked file changed. Making the ordering preserve its input reddened **two**
tests — the row ordering and the source ordering — and both were restored and
re-run green.

### The permutation point

The ordering property was first written with `random.shuffle` over a seeded
generator, twenty-four samples. Ruff refused it: `S311`, a pseudo-random
generator flagged as unsuitable. The repository's standing instruction is never
to silence a lint but to address what it points at, so the sample was replaced
with `itertools.permutations` over the whole input set.

**A random shuffle proves the ordering held on one arrangement per run;
exhaustive permutations prove it holds on all of them.** The lint pushed the
test from a sampled property to a total one. That is worth recording in those
terms because it is the first case in this campaign where obeying a lint made
the TEST strictly stronger rather than merely keeping the tree clean — the usual
outcome is that the lint is right about style and neutral about evidence.

The set is three items, so the exhaustive form is six orderings and costs
nothing. A larger set would need the sampled form back, and would then be
sampling deliberately rather than by accident.

## Notes

The module this landed in is co-authored. The runner half — the part that walks
a directory and executes the pipeline — arrived from a concurrent lane while
this was landing, and is not covered by this record. The ordering and identity
primitives, and the twelve tests over them, are the part this Step delivered.

Two lanes writing one module was a dispatch overlap rather than anyone's error,
and it was escalated rather than resolved locally. The runner half was sitting
untracked at the time, which in this tree means invisible to discovery and
unrecoverable if anything sweeps, so it was committed alongside this work with
its authorship stated in the commit message rather than left at risk.
