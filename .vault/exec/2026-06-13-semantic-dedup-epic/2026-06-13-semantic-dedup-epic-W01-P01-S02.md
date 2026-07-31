---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-07-04'
modified: '2026-07-04'
body_hash: 'sha256:093201ccc43149c12de571ca8332608788523eb049cfc3f62842f6dfb85fe38a'
step_id: 'S02'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

# Consolidate the duplicated _validate_nif/_validate_nie/_validate_cif core into one owning module and re-express the other module's validators over it

## Scope

- `src/aeat/core/identity/_tax_id.py`

## Description

- Extract the CIF Luhn-style checksum arithmetic into one owning primitive `_cif_check_value(digits) -> int` in the base module `_documents.py`, returning the raw check value in `range(10)`.
- Refactor `_documents._compute_cif_check` to delegate its arithmetic to `_cif_check_value`, keeping the strict current-spec digit-vs-letter rendering.
- Re-express `_tax_id._validate_cif` over the shared kernel: replace its inline even/odd doubled-digit loop with `_cif_check_value(digits)` and its local `_CIF_CONTROL_LETTERS` table with the imported `_CIF_LETTER_TABLE`, preserving its distinct legacy-tolerant leader dispatch and string return.

## Outcome

- The CIF checksum arithmetic and the `JABCDEFGHI` letter-control table live once in `_documents.py`; `_tax_id.py` consumes them instead of re-deriving them.
- Behavior-preserving: a full-space probe confirmed `_cif_check_value` and the removed inline `_tax_id` computation return identical values for every 7-digit body `0000000..9999999` (0 mismatches).
- Both public surfaces keep their exact accept/reject behavior: `_documents` still enforces strict current-spec per-kind rendering (digit-only `ABEH`, letter-only `PQRSNW`), `_tax_id` still enforces its legacy-tolerant dispatch (letter-only `PQRSNW`, digit-or-letter otherwise). Only the identical arithmetic is shared.
- The identity test suite passes (16 passed) and the registry NIF/scalar tests pass (91 passed); `ruff` and `ty` are clean.

## Notes

- Substitutability pre-filter: the two `_validate_cif` families are NOT freely substitutable — `_documents` requires a digit control for the `ABEH` leaders while `_tax_id` accepts either a digit or a letter for them, and the return types differ (`IdentityDocument` vs canonical `str`). Per the pre-filter these divergent dispatch/return shapes are left untouched; only the provably-identical checksum kernel (same arithmetic, same `JABCDEFGHI` table) was consolidated.
- This threads ADR F1 (keep both surfaces, no unsafe merge): the divergent CIF leader-set policy, return type, and error construction that F1 protects are preserved; the shared kernel extraction removes duplicated arithmetic without changing any accept/reject decision, verified by the full-space equivalence probe and the real identity test suite.
