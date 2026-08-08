---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:85b98994e9391ffdbf018d12e23c1ee416086a250d7736590dc295928ae43d9c'
step_id: 'S151'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Promote the classification criteria assembly onto the package facade

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add the criteria assembly's public surface to the ledger package facade: `assemble_classification_criteria`, `classify_from_assembled_criteria`, `ClassificationAssembly`, `MissingClassifierInput`, `DeclaredFact` and `DeclaredFacts`.
- Add `ClassifierInputs` and `collect_classifier_inputs` alongside them, since the promoted function takes the first as a required argument and a caller cannot produce one without the second.
- Register every promoted name in the lazy-export map and in `__all__`, so the facade's one canonical home per symbol is preserved and the eager import cost stays unchanged.

## Outcome

The assembly is reachable from the owning package's facade rather than from a private module. Before this row its only consumers were two test modules inside its own package, so the first cross-package consumer would have had to reach into `_classification_assembly`, which the import-hygiene gate forbids.

The promoted set is the usable one rather than the literal one. Promoting the function alone would have left a cross-package caller unable to build its required argument, which is the shape that produces a second private reach a week later.

The lazy-export map and `__all__` agree exactly: every promoted name resolves through the facade's `__getattr__` and appears in the public surface, with no name in one and not the other.

## Verification

The facade's two channels were reconciled programmatically after the edit, comparing the lazy-export keys against `__all__` in both directions:

    in lazy not all []
    dupes []

Resolution through the facade is exercised by the consuming row's suite, which imports the promoted ladder alongside them:

    uv run --no-sync pytest -n0 -q src/cadrumo/application/ledger/tests/test_establishment_ladder.py
    28 passed in 3.78s

The wider surface, under the default marker expression:

    uv run --no-sync pytest -n0 -q <ladder, counterparty establishment, classification assembly, declared facts, structured postal, domain iva tests, core identity tests>
    676 passed in 22.70s

## Notes

Landed with the consuming row rather than after it, which is what the precondition asks: a promotion that follows its consumer leaves a private cross-package import standing in the tree in between.

The facade file carries two lint findings, an unsorted import block and an unsorted `__all__`. Both are present at HEAD before this change with the same rules and the same count, and both would be resolved by a whole-file reordering that would sweep ordering owned by other lanes, so they are reported rather than fixed here.
