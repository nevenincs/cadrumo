---
tags:
  - '#reference'
  - '#m200-administradores-profile'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:21253db433cd3facf8d611cfdebfbce908b7cde4e63f258a7a3844d85201e9ab'
related: []
---

# `m200-administradores-profile` reference: `Modelo 200 page 002 export rows and their missing source`

## Summary

How Modelo 200 page 002 reaches the export file today, and where its source is missing. Observed on `lane/calc-iva` at f6f29e1885 with the sociedad-limitada persona.

- **The design declares page 002 required.** `m200-page-002` (`required = true`) and `m200-page-002b` are in the 2024 and 2025-y-siguientes export layouts (`src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/export/0004-record-m200-page-002.toml` to `0009-record-m200-page-002b.toml`, with the same files under `2025-y-siguientes`). The record list is in `0000-export-layout.toml:41`. Their fields are projections, by family and slot:
  - administrador, 5 slots: nif, apellidos_nombre_razon_social, forma_juridica, codigo_provincia, domicilio_fiscal, representante
  - participacion_socio, 6 slots
  - representante_legal, 3 slots: nif, apellidos_y_nombre, fecha_poder, notaria_otros
  - secretario_consejo, 1 slot
  - participacion_directa, 3 slots, 18 fields each
  - entidad_menor_dependiente, 10 slots
  - establecimiento_permanente, 18 slots
  - socio_sicav_disolucion, 5 slots

  The family and field sets of the two editions are identical. No family has a cargo field.
- **Typed rows exist; nothing fills them.** `Modelo200ProjectionRows` (`src/cadrumo/application/filing/producer_snapshot_m200.py:220`) defaults every family to empty and says the rows are operator-supplied. `Modelo200ProfileFacts` (`producer_snapshot_m200.py:256`) carries them. No production code constructed `Modelo200ProfileFacts`: `build_filing_producer_snapshot` raised `ValueError("modelo 200 requires Modelo200ProfileFacts")` (`src/cadrumo/application/filing/producer_snapshot.py:733`). That error was wrapped as `INTEGRITY_MODELO_EXPORT_DESIGN` with cause `snapshot_inconsistent` (`producer_snapshot.py:936`, `src/cadrumo/application/modelo/export_accounts.py:639`).
- **With the producer built, page 002 is absent.** The per-modelo dispatch `_resolve_export_model_profile` (`src/cadrumo/application/modelo/export_accounts.py:797`) given a `sociedades.annual` branch makes the 2025 sociedad export refuse with `REFUSED_MODELO_EXPORT_REQUIRED_RECORD_ABSENT`, "El diseño oficial exige al menos un registro m200-page-002".
- **The profile holds no such record.** The schema (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`, version 9 at line 3) has repeatable sections `attribution_entity_socios` (line 578), `attribution_received`, `activities`, `renta_inmueble` and `renta_arrendamiento`. None holds administrators or entity relations.
- **The persona states officers that never reach the profile.** The persona's `[[officers]]` block (`dev/fixtures/personas/sociedad-limitada/persona.toml:64`) is listed in `DECLARATIVE_BLOCKS` (`src/cadrumo/tests/personas.py:52`), so it is not materialised.
- **Stated absence, existing pattern.** The profile uses tri-state fields whose unanswered value is distinct from a stated no: `has_employees` (`schema.toml:1163`), and `colegio_concertado`, whose origin is read in `export_accounts._modelo_111_profile_facts`.
