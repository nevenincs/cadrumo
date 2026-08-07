---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b1d9bbb286fd0fd21667c60158b03b58775a0ac43dfb29e21652173d5f867992'
step_id: 'S50'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Flip the default vision model to the Apache-2.0 candidate and add the licence gate asserting no default candidate in any role carries a commercial-use bar, proven by mutation

## Scope

- `src/cadrumo/core/_config_runtime_fields.py`

## Description

- Source both local-model settings defaults from the catalogue instead of string literals.
- Flip the vision default to the Apache-2.0 candidate.
- Flip the text default to the Apache-2.0 candidate, which the gate's own scope requires.
- Rewrite the affected field descriptions to state the licence reason rather than only the hardware reason.
- Correct the memory-floor description, which was sized against the outgoing vision default.
- Add the licence gate over every per-role default and prove it by mutation.

## Outcome

The shipped vision default was a research-licensed model whose publisher text bars commercial use, inside a commercial tax product. The replacement is permissively licensed, smaller, and measured equivalent at this discipline, so the correction costs nothing in capability. This is the rare case where the compliant option is also the cheaper one.

The text default was barred too, and this was not in the original framing. The incumbent is one of exactly two sizes in its family released under the research licence rather than the permissive one — easy to miss precisely because the family reads as permissive. The gate's own wording covers every role, so it forced the second correction, and the second correction is the more valuable finding of the two: the first was known, the second was not.

Both defaults now read from the catalogue rather than from literals, so the settings surface and the licence gate cannot disagree about which model ships. A default naming a model the catalogue does not describe is refused at import.

The floor description had been sized against the outgoing vision default and would have overstated the requirement of the model that actually ships.

## Verification

Gate at `src/cadrumo/core/tests/test_model_catalogue.py`, asserted in two places that fail independently: over the catalogue's declared per-role defaults, and over the live settings values read through the production loader. The second closes a gap the first cannot see — the catalogue could be correct while a settings field still carried a hand-typed literal.

    uv run --no-sync pytest -p no:randomly -o addopts="-p no:cacheprovider" -m unit src/cadrumo/core/tests/test_model_catalogue.py src/cadrumo/application/tests/test_model_selection.py src/cadrumo/application/tests/test_provisioning_hardware_contention.py src/cadrumo/application/tests/test_provisioning.py src/cadrumo/llm/tests/test_local_text_reader_wiring.py -q
    87 passed in 31.75s

Mutation-proven from an out-of-repo plugin loaded on the path, so nothing under the source tree was edited and a crashed run would have left no residue.

Restoring the exact pre-correction state — the research-licensed model as the shipped vision default:

    1 failed, 37 passed in 13.14s

The single failure is the licence gate. It bites on precisely the state this Step corrects.

Keeping the default identifier but flipping the licence recorded under it:

    4 failed, 31 passed in 5.22s

The licence gate, the settings-agreement gate, and two selection-side gates. This proves the settings surface is covered independently of the catalogue's own default map, which the first mutation alone would not have shown.

## Notes

A hardware-floor gate elsewhere reddened as a consequence of the default move. It pinned model names to assert a floor property, so it broke on a default change that never touched the floor and taught nothing about it. It was rewritten to read each role's declared requirement from the catalogue and assert the property, and it now covers every role. A gate that pins the value of the thing it is not testing will keep reddening for unrelated reasons, and each red costs a sweep.
