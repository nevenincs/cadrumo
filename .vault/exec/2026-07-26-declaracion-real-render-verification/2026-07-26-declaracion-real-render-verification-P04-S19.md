---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S19'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Correct the Modelo 100 sidecar manifests to declare both sanitiser constants, since the length-preserving sanitiser wrote two forms while the manifests name one

## Scope

- `src/cadrumo/tests/fixtures/justificantes/100`

## Description

The three Modelo 100 sidecars named one replacement constant, `1.000,00`. The
sanitiser is length-preserving, so writing that constant into fields of differing
printed width renders two forms. Measured on the pages: `1.001.000,00` and
`1.000,00`, in counts 54/16, 59/15 and 59/19.

Nothing the manifests reported was false. They were incomplete as a description
of the document, which is a subtler failure and cost more: earlier in this
campaign a parser fix was judged incomplete for producing `1.001.000,00`, on the
reasoning that the declared constant was the only legitimate value. The page
carries `1.001.000,00`, so the criterion was wrong rather than the fix.

Scope was established before correcting anything. All nine `real_corpus`
specimens were measured, declared amounts against rendered ones: **Modelo 100 is
the only affected specimen.** Every other one renders exactly its declared
constant, and its rendered count matches its manifest's amount-replacement count
exactly -- Modelo 111 at 6, 6, 6 and 1, Modelo 190 at 4, Modelo 390 at 13. The
length-preserving behaviour only produced a second form where the original fields
were twelve characters wide, which among the bundled specimens happens on Modelo
100 alone.

## Outcome

Each Modelo 100 sidecar now declares the forms measured on its own pages, with
counts, under a key of its own rather than folded into `replacements_applied`.
That separation is deliberate: the replacement record is the sanitiser's audit
output, and a hand-derived measurement does not belong inside a tool's account of
what it did. The key carries a note stating it is measured from the render, that
Modelo 100 is the only affected specimen, and that a check grounded on the
declared constant alone is checking against an incomplete description.

The real-render gate reads both sources now, so for every unaffected specimen it
reduces to the single declared constant and nothing changes.

The effect on the Modelo 100 boundary gate was re-measured rather than assumed,
because the coordinator asked to be told if the fix underdelivered. It does not:
driving a repaired extraction over each of the three specimens previously made
**1 of 19** recovered targets agree, and now makes **19 of 19**. The gate rested
on one target and now rests on all of them. It still passes today -- the current
parser agrees on none of the 21 -- so what changed is the description of the
corpus, not the gate.

Verification: 249 tests pass across the declaración suite and the ledger evidence
corpus test that also reads these sidecars; `ruff` and `ty` clean;
`pytest --collect-only -q` exit 0 immediately before the commit.

## Notes

One thing this does not fix, and should not be read as fixing. The Modelo 100
manifests declare 124, 133 and 137 amount replacements while only 70, 74 and 78
amounts render. The counts do not reconcile, so a manifest entry cannot be mapped
to a rendered form one-to-one -- presumably because one printed amount can be
drawn by several content-stream operations. That is why the correction declares
the rendered forms as a measured set rather than repairing the individual
`replacements_applied` rows, which would have required an attribution the
evidence does not support.

The nine-specimen sweep is worth keeping as the reason to trust the scope: the
correction is confined to Modelo 100 because it was measured to be, not because
Modelo 100 was the specimen under investigation at the time.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on; every count here comes from size-aware word extraction over the bundled PDFs.
