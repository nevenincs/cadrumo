---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5396c10062088a4a72b85b3ea2a6b144a4143c91257ba53144acaf181d75c1cd'
step_id: 'S27'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S27

## Outcome

Recorded all three sweeps in the form this Step requires — each as a fragmented authority named or a near-neighbour proven not to cover the case, never as a bare "no duplicates found".

| Step | Surface | Result |
|---|---|---|
| `W06.P08.S24` | retencion derivation | Fragmented authority named — one concept, four owners, no single home |
| `W06.P08.S25` | IVA category and clave | Fragmented authority named — one correspondence, three encodings, two directions |
| `W06.P08.S26` | observation-to-casilla routing | Near-neighbour proven NOT to cover — canonical fold drops `category_id` |

## What the shape of these results says

None of the three is a live wrong figure, and stating that plainly is the point of the Step's framing. What each one is instead:

- **S24** is a concept with no owner rather than two owners — the weaker failure, and the one a duplicate-hunting sweep is least likely to name, because there is nothing to diff.
- **S25** is a genuine multi-encoding whose agreement is currently accidental: the reverse table is incomplete and its gap is patched by an adjacent special case rather than by the table.
- **S26** is the one that would have been actively harmful to "fix". Two folds that look identical differ in their grouping key, and the canonical one is the *less* expressive of the two.

The S26 result is why this Step's wording earns its keep. A sweep that reported "five copies of the casilla fold, retire four" would have been read as a cleanup and would have blanked provenance on a filing surface.

## Method

Semantic search by meaning first (`vaultspec-rag`, production-only), then `rg` and full reads at HEAD to confirm exact sites, then — for S25, where the answer turned on reachability rather than shape — tracing the persisted `operation_type` through the CLI to the resolver to establish that the coverage gap is currently unreachable rather than assuming either way.

## Cross-reference

A parallel five-concept sweep over the invoice and IVA surfaces is recorded at `2026-08-07-stray-concept-sweep-audit`, including the M347/M349 `operation_kind` silent-drop defect it found and the two duplicated policies since collapsed. The two sweeps overlap on the IVA clave surface and agree: `IntracomOperationType` and the 347/349 descriptive-token vocabularies are separate axes and must not be merged.
