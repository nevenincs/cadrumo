---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:955e91a5093bed54f28a364e4508cf051e87096a827adf919fa5969956aa389a'
step_id: 'S355'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Project the modelo's REAL section structure into the workspace schema facet, which is a separate gap from the section_path naming collision and must not be closed by the rename. Even with the field correctly renamed to a record-family label, the modelo's declared sections remain unavailable to any Workspace consumer, so an operator sees one group called casillas rather than the sections the modelo actually declares. The calc-sheets layout module already reads the real structure from the casilla definition, so the data exists and is reachable -- what is missing is a contributor path carrying it into an admission

## Scope

- `the workspace schema facet and its producer`
- `with the calc-sheets layout module as the worked example of reading the real structure`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/static_inspection.py`
- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/workspace_manifest.py`
- `verify:` `pytest test_workspace.py test_workspace_models.py entrypoints/tui/modelo` -> `206 passed`
- `verify:` `M130 2019-y-siguientes` -> `20 of 20 casillas carry a declared section`
- `verify:` `ruff check` on every touched file -> `equal to its HEAD baseline`

## Notes

Two contributor paths, each reading the section where it genuinely holds it.
`RegistryRevisionInspection` gained `casilla_sections`, populated from the SAME
`casillas_by_id(revision)` call the constructor already made and discarded all
but the keys of, so the ids and the sections cannot disagree. The graded
snapshot path reads `tuple(casilla.section)` directly, because it already holds
the definition; routing it through the inspection's copy would add a second
route to one fact for no gain.

`section_path` is documented as distinct from `record_family`, and the empty
case is defined rather than left ambiguous: a binding, formula, relation or
parameter is not placed anywhere in the modelo's printed structure, so an empty
tuple means THIS KIND OF RECORD HAS NO SECTION, never that a section was
dropped. That distinction is exactly what the name collision W03.P20.S354
resolved had destroyed, which is why that row insisted the two gaps be closed
separately.

A BLAST RADIUS IS NOT THE SET OF FILES EDITED. The first attempt was reported
complete on parse, lint and a data check showing every M130 casilla carries a
section -- and 93 tests then failed on ONE cause:
`workspace_manifest.py` classifies every root field of the inspection and
refuses one it cannot classify. Adding a field without enrolling it there is an
incomplete change. The manifest shares no identifier with anything edited, so
no symbol-level check could have found it; the gate refusing the unclassified
case is what found it, which is the behaviour this campaign keeps asking gates
to have. Enrolled, and the re-run is clean.

Re-attested through the owning edit verb after hand-authoring, so the body
fingerprint matches its stamp.

Re-attested through the owning edit verb; body fingerprint matches its stamp.
