---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0e8301a4cbd6c5c941e6cdf5466002201d8d67980abfc2099dc440de661a4b4f'
step_id: 'S38'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S38

## Outcome

**FETCH-GATED behind `S37`.** Nothing was authored, and authoring anything would have been the specific failure this Step's own wording warns against.

## Why no mapping was written

The Step requires the code-to-art-95-partition mapping to be grounded in the registry with its own `legal_refs`, "never inferred in code". Grounding needs the code set, and the code set is the artefact `S37` is gated on. Writing the mapping now would mean inventing which codes fall in which partition — precisely the fabricated grounding that `legal-grounding-verifies-bundled-authoritative-corpus` forbids, and it would sit beneath a rate screen where nothing downstream could detect the invention.

## The partition the mapping has to serve

Recorded so whoever lands `S37` knows what to check the table against before assuming it serves. RD 439/2007 art. 95 needs four boundaries, not one:

- professional activities at the general rate,
- the reduced inicio-de-actividad professional rate,
- art. 95.4.2.º sectoral activities at 2 per cent,
- the art. 95.4.1.º carve-out at 1 per cent for engorde de porcino y avicultura.

## The contingency the Step asks to plan for, stated concretely

"Plan for the refreshed table proving unable to serve at all" is a live possibility rather than a formality, and `W03.P04` already found the reason it might not serve.

The only bundled tipo-de-actividad enumeration today is the Modelo 840 IAE set: Empresarial, Profesional, Artística. That resolves professional against everything else — one boundary of the four — and carries no agrícola, ganadera or forestal value at all.

The cause is structural and predicts the outcome for any IAE-rooted vocabulary: agricultural activities are largely IAE-exempt, so an IAE-derived tipo set has no reason to carry an agrarian value. The same fact makes the profile `iae_epigraph` systematically empty for exactly the filers a sectoral screen must identify.

So if the M036 table turns out to be IAE-derived, it will fail the same way, and the answer is a different authority rather than a coarser mapping. Whoever lands `S37` should check the table against the four boundaries above **before** building on it, not after.
