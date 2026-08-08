---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c74d402c24df0b1302f6d9cf977480239bd407d077681412190be33a9846e68e'
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

The check lives in
`src/cadrumo/domain/calculations/registry/_validate_export_field_widths.py`,
invoked per field by the export section validator in
`src/cadrumo/domain/calculations/registry/_validate_exports.py` beside the
existing literal-length check, NOT in the module the Step row scopes.

It landed inside the section validator first and was extracted after the
reviewability gate refused it: the ruling table and its per-attribute rationale
carried the module to 343 lines against a 300-line ceiling. The ceiling's own
comment names raising the number as this gate's failure mode, so the number was
not raised. Extraction into a sibling private module matches the family the
package already uses for exemption, previous-filing, and relation-source
validation, and it keeps ONE authority: the section validator still calls the
check on every field it already walks, so there is no second traversal and no
second dispatch table. The two modules are 246 and 117 lines.

Semantic discovery surfaced the section validator, which neither the decision
record nor the
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

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py src/cadrumo/domain/calculations/registry/tests/test_registry_reviewability.py -n0 -p no:randomly
    54 passed in 49.58s

    uv run --no-sync python -m dev.docs.apidocs scaffold
    Scaffolded 2 changed stubs, left 1350 unchanged, removed 0 stale stubs.

Both regenerated stubs name the extracted module and nothing else, so they were
staged; no peer module's stub was touched.

## Notes

The measurement behind the abstentions turned up a second live divergence in the
same modelo, recorded in the research document: an envelope-open slot 17 bytes
wide bound to a 4-character filing year. Gating that attribute would refuse the
registry build until the declaration is restructured, which needs its own decision
and byte-level verification, so the gate abstains there and the divergence is
recorded rather than silently absorbed.

That abstention was correct only for as long as the divergence stood. Follow-on
work restructuring the page-000 envelope-open record into its published
field-by-field composite has since tightened both remaining rulings to real
widths, which is the outcome the abstention was holding the door open for. A
reader comparing this record against the current mapping should expect to find
the year and period-token attributes gated rather than abstaining.
