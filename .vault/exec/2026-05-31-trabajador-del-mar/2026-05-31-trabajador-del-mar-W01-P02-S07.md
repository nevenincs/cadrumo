---
step_id: "S07"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W01.P02.S07 step record

## Step

Write registry snapshot integrity test asserting all three binding entries resolve with legal_refs populated.

## Files Touched

- `src/aeat/domain/calculations/registry/test_trabajador_del_mar_profile.py` — extended with 6 S07 binding-integrity tests. File subsequently committed (alongside S03 content) by the docs agent commit `6bf66e223`.

## Commits

- S07 content authored inline after S03 commit `1c1a68a3b`
- Committed as part of `6bf66e223` — docs: add accurate docstrings

## Tests Added (S07 surface)

- `test_trabajador_del_mar_toml_declares_three_binding_entries` — verifies exactly 3 entries
- `test_art7p_binding_has_required_fields_and_legal_refs` — Art. 7.p) cap, formula, BOE citations
- `test_rebeca_binding_has_required_fields_and_legal_refs` — REBECA fraction, Arts. 73+75 citations
- `test_da41_binding_is_inactive_and_has_legal_refs` — DA 41 inactive status, dual BOE citations
- `test_no_da24_reference_in_trabajador_del_mar_toml` — DA 24 contamination guard on binding TOML
- `test_all_binding_entries_carry_nonempty_legal_refs` — universal non-empty legal_refs contract

## Outcome

14/14 tests pass (8 S03 + 6 S07). Zero DA-24 references in registry. Zero "dietas a bordo" references. Registry snapshot integrity verified against all three exemption binding entries with BOE-grounded legal_refs.
