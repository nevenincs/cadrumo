---
tags:
  - '#reference'
  - '#renta-minimo-ascendientes'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:23ae9eab76c06f6c7370cc6864438f3ddb195c906af9a12e9ad435a1c7ffb5f7'
related: []
---

# `renta-minimo-ascendientes` reference: `Ascendant facts in the profile, the Modelo 100 bindings and the official texts`

## Summary

On feature/tui the Modelo 100 boxes 0515 and 0516 (mínimo por ascendientes, state and autonomic parts) are operator inputs consumed by formulas (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/formulas/0001-declarations.toml:1052` and `:1068`); nothing derives them. The 2022 bindings read the ascendant row leaves `nif`, `apellidos_nombre`, `birth_date`, `discapacidad_clave`, `convivientes` and `fallecimiento` for the XML Ascendiente columns (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:508-563`); `discapacidad_clave` (PCTMINASDLG, line 541) is not declared by the profile schema.

On lane/calc-renta the S50 unit adds `rentas_anuales`, `declaracion_propia` and `discapacidad` to the ascendant row (`src/cadrumo/domain/contribuyente/ascendant_minimum.py:42-44`, `src/cadrumo/application/user_profile/ascendant_rows.py:79`). It derives `renta_family.ascendientes_minimos_aggregate` and `_autonomico` (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:37-47`) and withholds both when a row omits a deciding fact, with a `household_row_fact_unstated` note (`src/cadrumo/application/modelo/profile_minimo_ascendientes.py:236-290`). Unreadable stored values refuse (`:161`). The profile schema stays at version 9 there.

Personas: asalariada-familia has one ascendant (`dev/fixtures/personas/asalariada-familia/persona.toml:77`); on the lane it states `rentas_anuales` 7200.00 and `declaracion_propia` false. autonomo-electricista and autonomo-fontanero declare `ascendants = []` (`persona.toml:98` and `:80`), stated empty.

Official texts:
- LIRPF art. 59.1 and 59.2 (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-59.html.extracted.md`).
- Art. 61 normas 2ª, 3ª, 4ª and 5ª (`ley-35-2006-art-61.html.extracted.md`).
- Art. 60.2 amounts and the assistance increment in the Manual Renta 2025 part 1 (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:42486-42500`).
- The PCTMINASDLG key values 1 to 4 in the 2025 XSD (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:1510`) and the 2025 dictionary (`01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:42`).

Schema versioning: `src/cadrumo/domain/user_profile/schema_migration.py:1-5` states that a bump that changes what a stored value means carries its own transition. Schema 9 (`4fcce0fedb`) cleared a stored value that could not be converted and asked the operator again.
