---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bcd80f8550d2a150dda9ff046449bfc1918eb3cc6119135e67e0883a88c87503'
step_id: 'S01'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
---

# Re-declare field modelo-200-page-001b-draft-profile_tax_id-pos-141 as kind filler, dropping draft_attribute

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0003-modelo-200-page-001b.toml`

## Description

- Re-declare the page-001B position-141 field as `kind = "filler"`, dropping `draft_attribute`.
- Flip `required` to `false`, matching every sibling filler in the same record.
- Leave `offset = 141` and `length = 15` untouched; both are AEAT-correct for the slot.

## Outcome

The byte slot AEAT reserves for the mercantile group's ultimate parent company's
foreign tax identification number now renders as spaces instead of the
declarant's own Spanish NIF right-padded from 9 to 15. Field kind FILLER renders
a run of spaces unconditionally, so no disposition or group-membership signal is
needed to suppress it.

`required` moved to `false` because `required` is only consulted for HEADER
fields, and every sibling filler in the record declares `false`; leaving `true`
on a filler would have been a declaration with no reader and no sibling.

The field id was NOT renamed. It still reads `-draft-profile_tax_id-pos-141` on
what is now a filler, against siblings named `-filler-pos-N`. The governing
decision record constrains the change to the existing field id, and the id is
referenced nowhere else in the tree, so renaming would have been unsanctioned
scope. The width check keys on the draft attribute, never on the id, so the
stale name cannot make the gate misfire. Recorded as a follow-up in the research
document.

## Verification

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k grupo_mercantil_parent_tin -n0 -p no:randomly
    1 passed, 43 deselected in 55.35s

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export_completeness_gate.py src/cadrumo/application/filing/tests/test_export_completeness_sets.py src/cadrumo/application/filing/tests/test_fichero_boe_completeness_parity.py src/cadrumo/application/filing/tests/test_fichero_boe_export_roundtrip.py -n0 -p no:randomly
    25 passed in 48.64s

The completeness and parity gates matter specifically here: re-declaring a field
as filler could have removed a casilla the completeness manifest requires. It did
not, because the field was a draft field and never a manifest-tracked casilla.

## Notes

The change was authored AFTER its regression, so the fix was observed converting
a real red to green rather than being asserted correct. See the S03 record.

The content landed inside a peer's bare whole-index commit rather than the
explicit-pathspec commit prepared for it: the git index lock was held by a dead
holder for the whole window, and by the time it cleared a peer had swept the
working tree. The content in HEAD is byte-identical to what was verified.
