---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1189b996eefaa2dc3bff17de6cff50eb4475d7c8c159c0a9a88ef6e3680558c5'
step_id: 'S17'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Retype Justificante.csv onto AeatCsv, deleting the JustificanteCsv alias outright rather than re-pointing it, and delete its docstring claim that the receipt domain owns the bound because it owns the artefact the value is read from. That sentence asserts the ownership the 2026-08-10 ADR amendment overturns, and leaving it standing over a retyped alias leaves source prose describing the rejected design where the next reader meets it first

## Scope

- `src/cadrumo/domain/justificante/_schema.py`

## Description

This row was DELIVERED BEFORE THIS RECORD EXISTED. The record is reconstructed
from the history. This row carries two instructions that a commit could satisfy
independently, so both were checked separately against the tree rather than
inferred from one another.

`40c033eb9d` carried it, and it is the one commit in this Phase whose subject
names what it did.

The retype: the receipt record's `csv` field moved from the domain-local alias
onto the canonical one.

The deletion, first half: the domain-local alias was deleted OUTRIGHT. It was not
re-pointed at the canonical alias and not kept as a name forwarding to it. The
same commit removed it from the domain package's import list and from its
`__all__`, so the name resolves nowhere.

The deletion, second half: the alias's docstring went with it, including the
sentence claiming the receipt domain owns the bound because it owns the artefact
the value is read from. This is the half most easily missed, because deleting a
declaration deletes its docstring as a side effect - the row would also have been
satisfiable by a commit that re-pointed the alias and left that prose standing
over it, which is exactly the state the row exists to prevent.

The commit also swept the one consumer that imported the alias directly, the
submission record's `justificante_csv` field, moving it to the canonical alias in
the same index.

## Outcome

Delivered in full, both halves of the two-part instruction verified separately.

The retired alias name appears nowhere in the tree. The only surviving matches on
that string are a differently-named error class for a missing CSV, its registry
entry and its test references - a distinct symbol that shares a prefix, not a
residue of the alias.

The docstring sentence the row named is gone. No prose anywhere in the receipt
domain now asserts that the receipt domain owns the CSV bound. The ownership
claim the amendment overturned does not survive at the site a reader meets first.

The sweep of the direct consumer landed in the SAME commit as the retirement,
which is what the sibling row's tail note required: had it been deferred, the
retirement would have been a break rather than a deferral. It was not deferred.

No divergence between the row's instruction and what shipped.

## Notes

The commit message asserts that the storage-key precondition was discharged, on
the grounds that the CSV-keyed namespace has exactly one key-deriving consumer
and zero stored objects across every bucket, so normalising the value moves no
key and orphans nothing.

The zero-stored-objects half is the load-bearing one and it holds. The
one-consumer half does not survive re-measurement at reconstruction time: the
namespace has four write sites and two keyed-read sites across three modules.
That does not change the conclusion for data already on disk, but it does change
the surface a future key-composition change has to move, and it is why the
sibling enumeration row was worth doing on its own terms rather than treated as
closed by this commit's assertion. The enumeration row's record carries the
measured table, and a live read-write asymmetry it surfaced.
