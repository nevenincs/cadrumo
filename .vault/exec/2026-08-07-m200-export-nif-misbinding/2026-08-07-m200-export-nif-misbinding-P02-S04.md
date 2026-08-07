---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:45f727c14fd8b10c751f2b293696b96e4ac9a982dbbb38fe0ac5a80b2584616b'
step_id: 'S04'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
---

# Add a registry-build validator asserting a draft field whose draft_attribute resolves to a typed fixed-width source declares a matching length, starting with profile_tax_id against SubjectTaxId at 9 characters

## Scope

- `src/cadrumo/domain/calculations/registry/_export.py`

## Description

- Add a registry-build validator refusing a draft field whose slot width contradicts its typed source's canonical width.
- Rule per draft attribute in a mapping required to be total, so a new attribute without a ruling is refused rather than ignored.
- Promote the identifier width to a named export on the owning package facade and consume it, so the gate and the type share one authority.

## Outcome

The check lives in `src/cadrumo/domain/calculations/registry/_validate_exports.py`
beside the existing literal-length check, NOT in the module the Step row scopes.
Semantic discovery surfaced that module, which neither the decision record nor the
reference names, as the only export-field surface dispatched from the per-revision
validation dispatcher and therefore the only one that runs at registry BUILD over
every revision. The overlap check in the scoped module runs inside layout
resolution, which fires only when some caller resolves that one layout. Placing a
build-time gate there would have made it resolve-time-only and stood up a second
export-field validation surface beside the existing authority. Extending the
existing one was the deduplicating choice; the findability the Step row asks for
is served by cross-references in both directions instead.

The width ruling is keyed on the property, not on an inventory. It maps every
declarable draft attribute either to a width or to an explicit abstention, and a
runtime membership check refuses any attribute absent from it. Adding a new draft
attribute to the field schema without ruling on its width therefore fails
validation, rather than passing silently the way a list of currently-known-good
fields would. No count and no field-id allowlist appears anywhere in it.

The width has one home. The core identity package now exports the width its own
validator enforces, and that validator reads the constant, so the gate cannot
drift from the identifier contract. A second literal in the registry module would
have been the fragmentation this check exists to catch, one layer up.

Each abstention carries its own reason rather than a shared claim that these
attributes vary. That correction was material: the first draft asserted the
remaining attributes reach slots of several widths across the published designs,
and measuring the corpus showed otherwise. Two have no declarations at all, one is
uniform, and one diverges in a single declaration that is itself suspected wrong.
An abstention citing legitimate variability would have laundered a live defect as
expected diversity.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py -n0 -p no:randomly
    50 passed in 23.54s

## Notes

The measurement behind the abstentions turned up a second live divergence in the
same modelo, recorded in the research document: an envelope-open slot 17 bytes
wide bound to a 4-character filing year. Gating that attribute would refuse the
registry build until the declaration is restructured, which needs its own decision
and byte-level verification, so the gate abstains there and the divergence is
recorded rather than silently absorbed.
