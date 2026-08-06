---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-07-04'
modified: '2026-07-04'
body_hash: 'sha256:bd7c37e40a9c77ae1d290beb2a806e99edeede127a95a4926ce666f684d691bb'
step_id: 'S01'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

# Delegate _compute_nif_check_letter to the canonical nif_check_letter single source and remove the duplicate _NIF_LETTERS control-letter table

## Scope

- `src/aeat/core/identity/_documents.py`

## Description

- Promote the canonical NIF/NIE check-letter function `nif_check_letter` into the base module `_documents.py`, which already owns the `_NIF_LETTERS` control-letter table, so the table and its indexing function have one home.
- Delete the duplicate `_compute_nif_check_letter` function and route its three call sites (`_validate_nif`, `_validate_prefixed_nif`, `_validate_nie`) through `nif_check_letter`.
- Re-express the sibling `_tax_id.py` `nif_check_letter` as a re-export imported from `_documents.py` (dropping the second `_NIF_LETTERS[number % 23]` declaration) so external callers and the package facade keep their import path unchanged.

## Outcome

- One control-letter table (`_NIF_LETTERS`) and one check-letter function (`nif_check_letter`) for the whole `aeat.core.identity` package; the duplicate `_compute_nif_check_letter` and the duplicate `% 23` expression in `_tax_id.py` are gone.
- Ownership placed in `_documents.py` because it is the base module (`_tax_id.py` imports from it); placing the canonical function there avoids the circular import that would arise from `_documents.py` importing back into `_tax_id.py`.
- Behavior-preserving: a full-space probe confirmed the old `_compute_nif_check_letter` and the canonical `nif_check_letter` return identical letters for every integer in `0..99,999,999` (0 mismatches).
- The identity test suite passes (16 passed); `ruff check`, `ruff format --check`, and `ty check` are clean.

## Notes

- Substitutability pre-filter: the NIF/NIE check-letter computation is a pure function of `number % 23` over the shared `_NIF_LETTERS` table on both sides, so the two implementations have identical constraint shape and are freely substitutable; the full-space equivalence probe is the proof.
- ADR F1 keeps the two identity surfaces (`_documents` enum-returning strict-CIF, `_tax_id` string-returning legacy-tolerant) intentionally distinct; this step touches only the shared check-letter primitive, which the ADR names as already the correct single-source posture, so it strengthens that posture without collapsing the divergent surfaces.
