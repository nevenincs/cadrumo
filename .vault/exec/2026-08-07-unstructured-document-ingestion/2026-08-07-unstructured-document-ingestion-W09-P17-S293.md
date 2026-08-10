---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:4ba9f62f126a1caa92935464f10796f6592f1de52c4f407580439ad6cfce3f6a'
step_id: 'S293'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# The M390 casilla echoes: drained by authoring, not by nulling

## Scope

- `src/cadrumo/locales`

## Description

- Re-measure before converting anything, because the row proposes a mechanical change and a mechanical change against a stale premise is how a filing-grade surface breaks quietly.
- Classify every leaf in all four catalogues with the honesty gate's own predicate rather than a plain equality, since the shipped predicate folds a trailing dot or colon before comparing and a narrower probe would report a clean tree that is not clean.
- Find zero key-echoes, tree-wide and within the modelo-390 namespace, against a row that records 176 red at HEAD.
- Establish HOW they were drained, because the row's proposed method and the method actually used differ in a way that matters: they were AUTHORED, not nulled. A commit on 2026-08-08 authored real continuidad casilla labels in all four catalogues.
- Answer the row's open question separately rather than inheriting the answer from the drain, since the question outlives this particular backlog.
- Partition the residual null-valued modelo-390 leaves by key suffix, because the mandatory-Spanish-source contract binds titles, official names and labels, and not every key is one of those.

## Outcome

Nothing was converted and nothing needed to be. The backlog is gone and it went the right way.

**The row's open question is answered, and answered opposite to the fear that framed it.** Nulling a Spanish leaf WOULD trip the mandatory-Spanish-source contract where the leaf is a casilla label, so the row was right to refuse to run the conversion before settling it. But no Spanish label was nulled. Every unvalued Spanish modelo-390 leaf at HEAD is a help string — one hundred and ten of them, and one hundred and ten of one hundred and ten — while every modelo-390 label carries authored Spanish. So the honesty ratchet and the Spanish-source contract are simultaneously satisfied, which is exactly the state the proposed conversion could not have reached: nulling would have satisfied the ratchet by breaking the contract.

That is worth stating plainly because the row called the conversion "mechanical and honest". It was mechanical. On a label it would not have been honest, and the row's own instinct to gate it on that question is what prevented the damage.

**What this excludes, and it is not small.** This closes modelo 390. The same measurement surfaced a separate, unrelated breach of the same contract that this row does NOT cover and this lane does not own: three keys in modelo 303 — a casilla label, a construct field title and a revision field label — carry no value in ANY of the four catalogues. That is the highest-traffic modelo carrying three operator-facing names with no mandatory Spanish source. It is reported rather than fixed here, both because it is another lane's territory and because authoring a Spanish casilla label is registry-grounded work rather than a locale edit.

## Verification

Measured at HEAD `613973cc50`, parsing all four catalogues and classifying every leaf with the gate's own predicate:

    key_echo, tree-wide          es 0    en 0    ca 0    hu 0
    key_echo, modelo-390 only    es 0    en 0    ca 0    hu 0
    modelo-390 leaves            es 356 keys, 246 authored, 110 null
    null modelo-390 leaves by suffix, es    help 110    label 0    title 0

Draining commit, by another lane:

    02753ace17  2026-08-08 18:20  fix(locales): author real M390 continuidad casilla labels in all catalogues

Residual contract breach, reported not fixed, same measurement:

    modelo.schema.303 ... casilla.112.label                          null in all four
    modelo.schema.303 ... construct ... field.title                  null in all four
    modelo.schema.303 ... revision ... field.label                   null in all four

Gate run requested from the single test-run authority rather than executed here.

## Notes

Both this row and its sibling ratchet row were authored against true measurements that expired underneath them. The tell in both cases was only available by re-running the measurement with the SHIPPED predicate; reading the row, reading the catalogues by eye, and reading the plan all left the stale premise intact.

The near-miss is the part worth carrying forward. Had the conversion run against the row's own description of the work as mechanical, it would have nulled Spanish labels to satisfy a gate that was already green.
