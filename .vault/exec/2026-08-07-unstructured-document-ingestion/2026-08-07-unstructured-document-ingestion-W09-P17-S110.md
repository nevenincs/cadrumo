---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:12b37a6e8e4bb82eb85821ffe6e5b7f22c8f65a4abc76be9e0b2962e1792e8d2'
step_id: 'S110'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Context

Reconstructed by the coordinator, verified against HEAD, rather than authored by
an implementer. No lane took this row: it was opened after a lane reported the
false positive while closing a different Step, and it was satisfied by a
concurrent commit from another campaign before anyone claimed it. The record
exists so the row is not checked on an unexamined green.

## What was wrong

The code-set singularity detector keyed on the frozenset of stringified members
and flagged any module whose syntax tree enumerated a superset. The vinculada
taxonomy is eight bare capital letters, A through H, so the detector reported
that set as declared in three modules.

Only one of the three declared it. The other two were the Modelo 190 and 193
clave de percepcion, grounded in Orden EHA/3127/2009, and the Modelo 347 clave de
operacion, grounded in Orden EHA/3012/2008 — independently grounded AEAT
catalogues that happen to use letters. As the reporting lane put it, a
singularity gate keyed on bare single letters cannot discriminate between AEAT
code catalogues, because that is what AEAT code catalogues are made of.

## Why the row said not to deduplicate

The red was of the class where obeying it causes the damage. The obvious
resolution — remove the apparent duplicate — would have deleted a correctly
grounded Modelo 190 enum to satisfy a mis-keyed detector, in a commit that reads
as tidy-up. A lane triaging a red tree without the analysis would plausibly have
taken that path, so the prohibition was written into the row itself rather than
left in a report.

## How it was resolved

Commit `4b8a256f17`, "key the code-set singularity on equality, not containment":
133 insertions against 11 deletions on the gate's own test module. The detector
now matches on set equality rather than containment, so a catalogue that merely
shares letters no longer registers as a declaration of a different catalogue.

The change also introduced a helper that runs the real detector over a synthetic
tree of source files, which means the detector is now exercised against
constructed cases rather than only against the live tree. That is what satisfies
the row's requirement that a genuine second declaration of the vinculada set
still reds — the property is checked against inputs built for the purpose rather
than inferred from the absence of a failure.

## Verification

Both grounded enums survive at HEAD: `RetencionClave` in `core/aggregation.py`
and `_M347_CLAVE_OPERACION` in `domain/modelos/_row_models.py`. That is the
load-bearing check, because the failure mode this row guarded against was their
deletion rather than the gate staying red.

The gate itself: six collected, six passed, sequential, cache provider disabled,
where the same selection previously reported one failed and two passed. The
count rose because the re-key added constructed cases, not because assertions
were relaxed.
