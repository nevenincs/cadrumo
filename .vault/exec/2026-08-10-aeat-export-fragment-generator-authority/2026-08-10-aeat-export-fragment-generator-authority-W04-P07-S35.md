---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:244daf2b19d3516e5de86eb46bba94c72208bbabfb916497311116184da8a98f'
step_id: 'S35'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Pin every Modelo 303 official record-design source to its explicit `record_design_epoch`

## Scope

- `src/cadrumo/_data/registry/aeat/legal/iva.toml`
- `src/cadrumo/domain/calculations/registry/tests/test_record_design_source_selection.py`

## Description

- Add explicit `2023`, `2024-early`, `2024-late`, `2025`, and `2026` epochs to the five Modelo 303 official record-design catalogue sources.
- Exercise every pinned bundled binary through `resolve_record_design_binary` and independently compare its bytes and SHA-256 metadata.
- Prove overlapping 2024 source windows are separately verifiable only by their authored source reference and epoch, without date-only selection.
- Add real refusal coverage for epoch mismatch, absent epoch, SHA drift, and filename-as-source-reference input.
- Constrain the resolver to its catalogue-only import, global, direct-call, and attribute-call surface so authority, loader, export-layout, facade, cache, dynamic-import, and fallback paths cannot re-enter unnoticed.
- Resolve two independent-review medium findings by strengthening the structural negative gate; the final follow-up reported no critical, high, or medium findings.

## Outcome

The five Modelo 303 record-design sources now carry explicit epochs. `resolve_record_design_binary` remains an explicit-source verifier: it does not choose between overlapping catalogue entries or consult a registry revision or export layout.

Focused verification passed:

- `pytest src/cadrumo/domain/calculations/registry/tests/test_record_design_source_selection.py -q` - 16 passed.
- Combined source-selection, record-design-intermediate, and generator IR tests - 23 passed.
- Anti-false-green mock, monkeypatch, skip/xfail, and tautology ratchets - 51 passed.
- Ruff, format, basedpyright, and `git diff --check` passed.

## Notes

- The broader layout-applicability set reached 50 passes and one expected red: current spanning Modelo 303, Modelo 200, Modelo 390, and Modelo 720 revisions claim years outside their declared record-design source window. The Modelo 303 portion is the explicit S36 relayout obligation and was not masked by this step.
- A serial full registry collection initially hit an unrelated `CalculationRevisionId` facade-import error. No out-of-scope code was changed.
- No compatibility path was added and no legacy surface was retained by this step.
