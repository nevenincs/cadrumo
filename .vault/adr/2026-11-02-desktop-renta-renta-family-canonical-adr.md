---
tags:
  - '#adr'
  - '#desktop-renta'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:4f427c3ed98c0b22408a9f7a9276a9c6b8057b5b897b2d80ad993807ac7b0e5d'
related:
  - "[[2026-11-02-desktop-renta-adr]]"
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-adr]]"
  - '[[2026-11-02-desktop-renta-reference]]'
---

# `desktop-renta` adr: `renta_family descendiente and ascendiente objects are the canonical household rows` | (**status:** `accepted`)

## Problem Statement

The 2025 Modelo 100 child and ascendant boxes (NIFDLG, APENOMDLG, FNACDLG, MINUSDLG, FALLDLG, DNIASDLG, APENOMDLG_ASC, ANOASDLG, PCTMINASDLG, CONVASDLG, FALLASDLG) appear in `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/form_layouts/0001-form-layout.toml` only as `working_figure` placements. Their bindings (`renta-family-descendant-*` and `renta-family-ascendant-*` in `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`, inherited into 2025) read the `RentaFamilyProfile.descendants` and `.ascendants` arrays, which nothing in production writes. The setup wizard, the profile commands and the calculation all store descendants as the `renta_family.descendiente.{n}.{leaf}` object with `renta_family.descendientes_count` (`src/cadrumo/domain/contribuyente/descendant_facts.py`, `src/cadrumo/application/modelo/profile_export_binding.py:381-390`). The form therefore cannot serve the household rows the desktop Renta workspace needs (`2026-11-02-desktop-renta-adr`), and the profile shape the bindings read is a persisted-schema question. The operator ruled on 2026-11-02 that the written `renta_family.descendiente` and `renta_family.ascendiente` objects are the canonical profile shape for descendants and ascendants.

## Considerations

- Only `renta_family.descendiente` is written; the schema declares no `renta_family.ascendiente` object and nothing writes one (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`, `src/cadrumo/application/user_profile/family_rows.py`).
- The profile provider rejects unknown selector keys (`src/cadrumo/domain/calculations/registry/profile_bindings.py:29`), and its collection shape names a typed model attribute path, not a stored fact path.
- The form generator groups repeating rows only for bindings whose selector names `record`, `grouping` and `target_casilla_id` (`dev/registry/form_layout/page_sections.py:327-379`), the dictionary parser leaves asterisk boxes such as `*75` without a casilla, and no rule reads the design's repeat limits.
- The official repeat limits are in the 2025 XSD (`03-100-esquema-xsd-ejercicio-2025-...xsd`): Hijo 15, Ascendiente 4, DeducDescendienteDiscRes 15, DeducAscendienteDiscRes 4, ElementoInmueble 80, ElementoPatrimonial 80.
- The form read model reported a row group with no saved rows as known-empty (`src/cadrumo/application/modelo/work_form_records.py:225-247`), which draws an unanswered household like a declared empty one (`2026-09-30-modelo-editor-workbench-adr`).
- Some official columns have no canonical stored leaf: the descendant and ascendant name, and the disability clave, which is not the stored statutory grade.

## Considered options

- **Keep the arrays as the binding source.** No schema change, but the bindings keep reading a shape nothing writes, so every household row stays unknown. Rejected by the operator ruling.
- **Write the arrays as a second copy of the household.** It would satisfy the bindings but create two stores for one fact that must agree. Rejected.
- **Repoint the bindings to the written objects through a typed row selector.** One stored shape, read by the wizard, the calculation and the form alike. Chosen.

## Constraints

- `renta_family.descendiente.{n}.{leaf}` with `renta_family.descendientes_count`, and `renta_family.ascendiente.{n}.{leaf}` with `renta_family.ascendientes_count`, are the canonical household rows. The `renta_family.descendants` and `renta_family.ascendants` arrays are not a source for any binding; they stay declared only until their label keys are repointed, and must not gain a writer.
- A profile binding reads a household row through a typed repeating selector naming the object, one leaf and the object's count path. The provider's strict key check is not loosened.
- Leaves are the stored leaf names of the object. For descendants they are those of `src/cadrumo/domain/contribuyente/descendant_facts.py` (`nif`, `birth_date`, `fallecimiento`). The ascendant object uses the same names for the same meaning (`nif`, `birth_date`, `fallecimiento`) plus `convivientes` for the number of descendants the ascendant lives with. An official column with no stored leaf of the same meaning is bound to a reserved leaf that nothing writes (`apellidos_nombre` for the name, `discapacidad_clave` for the official disability clave). Its cells read unknown and are never filled from a leaf of another meaning, such as the statutory grade stored in `discapacidad`.
- A row group with no saved rows is unknown. It is known-empty only when the calculation persisted a positive enumeration by its source, such as a stated zero count.
- Row groups for official repeating elements come from a generic generator rule bounded by the design's repeat limits, with no modelo branch.

## Implementation

We will add a typed repeating row selector to the profile provider, repoint the descendant and ascendant bindings to the objects, and declare the `renta_family.ascendiente` object and `renta_family.ascendientes_count` in the profile schema without a writer. The profile resolver will emit row values for every repeating profile binding and record a source trace that names the group's boxes when the object's count is stated, so the form can tell proven-empty from unknown. The form generator will anchor asterisk boxes whose dictionary field names the declared casilla, and open one repeating group per official repeating element over its row-set boxes, with `max_rows` taken from the XSD. A writer for ascendants, and leaves for the name and the disability clave, are later work.

## Rationale

The written objects are the only household facts the profile holds, and every other consumer already reads them. A second store would need reconciliation forever; a typed selector keeps one shape and keeps the provider strict.

## Consequences

- Benefits: the form serves descendant rows from the facts the filer already entered, bounded by the official limits, and an unanswered household is no longer drawn as empty.
- Costs: ascendant rows stay unknown until a writer exists, and the name and disability clave columns stay unknown until their leaves are written.
- Reconsider if AEAT changes the household elements so that a row no longer maps to one stored object entry.
