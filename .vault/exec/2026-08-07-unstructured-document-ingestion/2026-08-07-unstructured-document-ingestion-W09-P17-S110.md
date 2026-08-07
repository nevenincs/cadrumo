---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:adb99c4370fa8b5f899812d6309cbeb1a8716003c8e1c4f2530db5cdc2121f5b'
step_id: 'S110'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Context

The row was opened after a lane reported the false positive while closing a
different Step, and the same lane then took and delivered it. An earlier version
of this record stated that no lane took the row and that a concurrent commit from
another campaign had satisfied it. That was wrong: `4b8a256f17` is the reporting
lane's own commit. The misattribution is recorded here rather than quietly
overwritten, because a record that credits the wrong author is the kind of error
this campaign has spent the day refusing to leave standing.

## What was wrong, and it was wider than the reported red

The code-set singularity detector keyed on containment: it flagged any module
whose syntax tree enumerated a superset of a canonical set's stringified members.
Measured across all three code sets rather than only the one that reddened:

| set | key | containment | equality |
| --- | --- | --- | --- |
| vinculada types | eight bare letters A–H | 3 modules | 1 |
| vinculada operation types | `01`…`11` | 4 modules | 1 |
| valuation methods | `1A`…`1E` | 1 module | 1 |

Six false positives across two sets. The reported instance named the Modelo 190
and 193 clave de percepcion, grounded in Orden EHA/3127/2009, and the Modelo 347
clave de operacion, grounded in Orden EHA/3012/2008 — independently grounded AEAT
catalogues that happen to use letters.

The clearest specimen is not either of those. The twenty-one-member standard
period codes were being reported as a re-declaration of the operation-type table,
purely because both begin `01`, `02`, `03`. The valuation methods passed all
along only because `1A`–`1E` happens to be distinctive, which is to say the gate
was correct by luck on the one set it did not flag.

## Why deduplicating would have been the damage

The row carried an explicit prohibition because obeying this red causes the harm
it appears to prevent. Removing the apparent duplicate would have deleted a
correctly grounded Modelo 190 enum to satisfy a mis-keyed detector, in a commit
that reads as tidy-up.

The semantic distinction the fix rests on: a duplicate declaration re-spells the
same table, while a superset is a different and larger table. Containment cannot
express that; equality is what the gate's own docstring already meant by refusing
a module that re-spells a canonical table.

## One asymmetry that would have emptied the detector

The canonical enums carry a not-declared sentinel that the key drops. Comparing
raw literal sets would therefore have made the one module that should match the
only one that does not — turning the detector into a vacuous pass while looking
stricter. Falsy literals are now dropped on both sides, and that is pinned rather
than left to a comment.

## Proofs

The detector takes a root, so its cases run over a synthetic tree of source
files. That is the change that makes it aimable: a detector that can only run
against the real tree can be shown to be quiet, never to be right, and quiet is
exactly what a mis-keyed detector looks like.

Three cases: a genuine second declaration still reds in both real shapes, an enum
class under a different name and a literal alias; the wider same-alphabet
catalogue does not red, planted so the shipped false positive cannot return; and
the sentinel does not hide the canonical home.

Mutation applied from outside the repository with the binding asserted before the
run: restoring containment reproduces the original failure message verbatim and
reds the false-positive proof, while the true-positive proof passes under both
rules. That asymmetry is the evidence the re-key narrowed the detector without
blinding it.

Six collected, six passed, where the same selection previously reported one
failed and two passed. The count rose because constructed cases were added, not
because assertions were relaxed.

## Verification of the load-bearing property

Both grounded enums survive at HEAD: `RetencionClave` in `core/aggregation.py`
and the Modelo 347 clave literal in `domain/modelos/_row_models.py`. That is the
check that mattered, because the failure mode this row guarded against was their
deletion rather than the gate staying red.
