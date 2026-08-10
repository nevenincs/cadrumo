---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:1c9b71b448b616d11a5a6324b7b391d12fefc36587a926c6f86b7dae153481aa'
step_id: 'S14'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Prove missing, duplicate, ambiguous, fuzzy, and illegal-exception mappings refuse the whole design

## Scope

- `dev/registry/tests/`

## Description

- Add whole-design refusal tests for missing and duplicate semantic-map anchors.
- Add an exact-cell near-match mutation and an ambiguous parser-anchor mutation.
- Prove a valid hash-pinned anomaly explanation cannot supply missing semantic meaning.
- Extend the structural red guard to reject restored single-file, direct-revision, and fuzzy-matching surfaces.
- Run the independent S14 audit against the accepted authority contract.

## Outcome

The join now has direct adversarial proof that it refuses before constructing any partial design when map coverage is missing or duplicated, parser anchors are ambiguous, or a candidate differs only by its workbook cell. A valid anomaly exception still cannot waive a missing mapping. The structural guard makes restored legacy-loader and heuristic matching tokens fail the test suite.

Focused proof passed: `uv run --no-sync pytest -q dev/registry/tests/test_semantic_map.py dev/registry/tests/test_semantic_map_validation.py dev/registry/tests/test_semantic_map_join.py` reported 36 passed. `ruff check`, `ruff format --check`, and `basedpyright` were clean for the changed test surface. The independent audit found no issues.

## Notes

No production behavior changed. The initial adversarial parser fixture used JSON-mode values that strict models correctly refused; it was rebuilt from the native typed payload before the recorded proof run.
