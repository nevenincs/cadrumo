---
step_id: S106
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P31.S106 step record

## Step

Re-run all 10 diagnostics clauses against the full tree as an honest W11 gate
re-assertion. Confirm zero violations. Document actual counts.

## Results

All 10 clauses pass with zero violations:

| Clause | Detector | Result |
|---|---|---|
| C1 | find_sibling_domain_id_imports | 0 violations |
| C2 | find_private_id_imports | 0 violations |
| C3 | find_misplaced_hex_length_constants | 0 violations |
| C4 | find_bare_str_typed_id_fields (with PROMOTE001_PROTECT_LIST) | 0 violations |
| C5 | find_sibling_domain_enum_imports | 0 violations |
| C6 | find_sibling_domain_constant_imports | 0 violations |
| C7 | find_sibling_domain_protocol_imports | 0 violations |
| C8 | find_private_name_cross_package_imports | 0 violations |
| C9 | find_same_name_constant_multi_declarations | 0 violations |
| C10 | find_bare_str_kind_status_state_fields | 0 violations |

pytest output: `21 passed in 11.90s`

The W11 gate is now honestly green: all 10 clauses assert zero violations against
the real post-S104/S105 tree. The public-surface pin test (`test_detector_public_surface_is_pinned`)
updated to include `PROMOTE001_PROTECT_LIST` in the expected surface.

## Files touched

- `src/aeat/diagnostics/test_identity_primitive_placement.py` — updated public-surface pin
  to include `PROMOTE001_PROTECT_LIST` and updated import.
