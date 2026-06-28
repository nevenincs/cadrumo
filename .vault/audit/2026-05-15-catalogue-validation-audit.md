---
tags:
  - '#audit'
  - '#catalogue-validation'
date: '2026-05-15'
modified: '2026-05-15'
related: []
---



# `catalogue-validation` audit: `M130/M131/M202/M303 catalogue-validation gap diagnosis`

## Scope

Read-only diagnosis of the 73 validation failures raised by
`test_catalogue_verification.py` on `chore/eliminate-shims` at HEAD
`fa354477`. No source mutation; this document classifies the failure
families and points to the canonical fix for each. Mutations are
deliberately left to the agents already working in adjacent regions.

## Findings

The 73 failures partition into four independent gap families.

### F1 — self-relation `source_periods` missing (6 relations)

Validator `_validate.py:1046` requires every relation to declare
`source_periods` explicitly. Six `previous_quarter` self-relations
populate `source_period_offset_from_target = -1` and
`target_periods = ["2T", "3T", "4T"]` but leave `source_periods` empty,
expecting the offset to imply `["1T", "2T", "3T"]`. The validator does
not derive the implicit set.

Affected: M130 `modelo-130-rel-self-prior-quarter-negative`, M131
`modelo-131-{2019-2023,2024,2025,2026}-rel-self-prior-quarter-negative`,
M303 `modelo-303-rel-self-compensacion-anteriores`.

### F2 — M131 phantom `-v101` source-ref suffix (12 errors)

The casilla `saldo-negativo-fin-periodo` and the formula
`modelo-131-{year}-saldo-negativo-fin-periodo` in M131 2024 / 2025 /
2026 reference source id `aeat-dr-131-{year}-v101`. That id does not
exist in the catalogue; the actual layout source is
`aeat-dr-131-{year}` (no `-v101` suffix). The `-v101` form survives
correctly only on `aeat-dr-131-2019-2023-v101`. Each year emits two
unknown-id errors plus two construct source-ref closure errors, for a
total of 12 errors across 2024 / 2025 / 2026.

### F3 — M202 construct source-ref closure (8 errors)

In M202 revisions `2019-2022` and `2023-2024`, the construct
`modelo-202-{revision}-foundation` omits source ref
`aeat-modelo-202-instructions` even though the binding
`pagos-fraccionados-anteriores`, the relations `rel-self-pagos-2p` /
`rel-self-pagos-3p`, and the dependency classification
`dep-self-prior-pagos` all declare it as a required source. Closure
check fails 4 times per revision.

### F4 — M303 missing LIVA articles in legal catalogue (~47 errors)

`registry/aeat/legal/iva.toml` carries only three LIVA entries today
(`art-163-octiesdecies`, `art-163-unvicies`, `art-163-quinvicies` —
regime-especial articles only). M303 references the core deduction
and prorrata authority articles which are not yet catalogued:

- `ley-37-1992:art-99` — IVA deducible (compensación-anteriores,
  resultado, compensación-disponible-fin-periodo)
- `ley-37-1992:art-102` — prorrata aplicable
- `ley-37-1992:art-104` — prorrata general
- `ley-37-1992:art-107` — regularización deducciones bienes inversión
- `ley-37-1992:art-108` — concepto de bienes de inversión
- `ley-37-1992:art-109` — procedimiento de regularización
- `ley-37-1992:art-110` — entregas durante el período de
  regularización

These articles are referenced across casillas, formulas, binding,
and the M303 self-relation, producing the bulk of the failure count.

## Recommendations

F1 — populate `source_periods = ["1T", "2T", "3T"]` on each of the
six self-relations. Strictly mechanical; matches the implicit offset
semantics already documented in `period_alignment.mode`. The same
edit unblocks F4's `relation modelo-303-rel-self-compensacion-anteriores
references unknown legal id` line that compounds the M303 LIVA-article
gap (the relation will still fail until F4 lands).

F2 — substitute `aeat-dr-131-{year}-v101` with `aeat-dr-131-{year}` on
M131 2024 / 2025 / 2026 casilla `saldo-negativo-fin-periodo` and the
matching formula. Verify construct `modelo-131-{year}-objective-
estimation-instalment` source_refs covers the corrected id (already
listed in the construct per inspection).

F3 — add `aeat-modelo-202-instructions` to the M202 2019-2022 and
2023-2024 construct `source_refs` arrays. Source id already exists; the
omission is closure-only.

F4 — author seven new `[legal."ley-37-1992:art-NN"]` entries in
`registry/aeat/legal/iva.toml` grounded in the BOE consolidated text of
Ley 37/1992. Largest of the four; produces ~47 of the 73 errors. Should
be paired with corpus HTMLs under `corpus/normatives/html/` matching
the established pattern of the existing LIVA art-163 entries.

The four families are independent — any agent can pick any one without
blocking the others. F1 / F2 / F3 are mechanical TOML edits in modelo
files; F4 requires a corpus-grounded legal catalogue extension.
