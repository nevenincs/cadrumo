---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:ad8fcdf3c9096c9eab8721d4fa839ccfb0d105f30cb806f414b58ec3e0414726'
step_id: 'S477'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Reinstate the two Modelo 200 unadjudicated repeated slot entries that a re-authored export layout brought back, confirming against the design the revision actually cites that each slot carries a separate figure under its own label rather than a part of one value, so a part policy would be wrong and the question stays open

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_export_split_part_rendering.py`

## Changes

Both `test_a_multi_field_casilla_either_splits_one_value_or_is_declared_unadjudicated`
cases pass; 162 tests in the owning suite pass.

THE FILE PREDICTED THIS FIRING. A comment in it recorded that two Modelo 200
entries had been removed from `_UNADJUDICATED_REPEATED_SLOTS` because both
revisions declared ZERO export layouts, kept the reasons rather than deleting
them, and said in as many words that "re-authoring the Modelo 200 layout brings
both questions straight back". A layout has since been re-authored, the repeated
slots are live again, and the two questions came back exactly as written.

I CONFIRMED THEM INDEPENDENTLY BEFORE REINSTATING, because a note left by a
previous author is orientation, not proof. Read from the design the revision
CITES -- `2025-y-siguientes` declares `aeat-dr-200-2025`, not the 2024 design
where both numbers also appear on other pages:

    DP200015B  585 | 7 | Deducciones doble imposicion interna - Tipo de gravamen 2025 [00103]
    DP200015B 1452 | 7 | ... (DT 23.1 LIS) - Tipo de gravamen 2025 [00103]
    DP200015B 2349 | 7 | ... internacional RDLeg. 4/2004 - Tipo de gravamen 2025 [00103]

    DP200045   880 | 17 | Perdidas fiscales a compensar [00199] Aplicable a IIC financieras
    DP200045   897 | 17 | Perdidas fiscales a compensar [00199] Aplicable a IIC inmobiliarias

Each slot carries its OWN label and its own scope. These are separate figures
sharing a printed casilla number, not parts of one value, so the gate's other
route -- authoring part policies -- would have been wrong rather than merely
premature.

THE GEOMETRY WOULD HAVE MISLED ME, and that is why the design was consulted.
00199's two slots are CONTIGUOUS (880 + 17 = 897) and identically typed, which
is exactly what an integer/decimal pair looks like to anyone reading offsets. It
is the design's labels, not the offsets, that show them to be IIC financieras
and IIC inmobiliarias.

Reinstated with the reasons verbatim from the note, and the note rewritten to
say the entries are live again and how they were re-confirmed.

Teeth, two directions, each restored by copy:

* removing both entries again fails the gate -- the defect verbatim;
* pointing an entry at a slot group that does not exist
  (`m200-page-999`) fails `test_no_unadjudicated_entry_is_stale`. That second
  gate is the one that removed these entries the first time, so proving it still
  bites is what stops the declaration becoming a place to park dead exemptions.

## Notes

WHAT REMAINS OPEN IS FILING-GRADE AND UNCHANGED. Neither question is answered by
this step; both are recorded as open with their reasons. 00199 needs a casilla
per institution type in the generator's semantic map -- a modelling change to a
generator-owned tree. 00103 asks whether one entity can carry three different
rates across three deduction blocks, which is a tax review. Recording them is
the honest state, not a fix.

STILL OPEN: the export-tree group stopped in S472 and characterised in S474,
`test_config_reset_lifecycle::test_config_reset_start_status_and_resume_exact_durable_journal`
(verified pre-existing in S476), and the three operator decisions -- the 125
`cli.*` extras, the 5 `application.*` extras, and the
`tui.ledger.reconciliation.direction` spelling.
