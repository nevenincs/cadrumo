---
tags:
  - '#adr'
  - '#m200-administradores-profile'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:d5e80dded0f3d94637e709ac7184b98a4bdf271d4fddd412940aff46fccc35bf'
related:
  - "[[2026-11-02-casilla-value-absence-adr]]"
  - "[[2026-07-26-censal-profile-autofill-adr]]"
  - "[[2026-08-07-m200-export-nif-misbinding-adr]]"
  - '[[2026-11-12-m200-administradores-profile-reference]]'
---

# `m200-administradores-profile` adr: `Modelo 200 page 002 rows as profile facts` | (**status:** `accepted`)

Accepted 2026-11-12 13:15 by PRIME on the operator's delegated authority, with conditions (g) to (j) below; (h) as corrected at 13:15 from ACCEPTANCE's citations of the 2024 sociedades manual.

## Problem Statement

The DR200 design declares the page 002 record (`m200-page-002`, `m200-page-002b`) required in every edition the registry exports. It carries the administradores and the other relations of the entity. The export reads these rows from `Modelo200ProfileFacts.projection_rows` (`src/cadrumo/application/filing/producer_snapshot_m200.py:220`), and nothing fills them: the taxpayer profile holds no administrator or relation record. Once the producer snapshot is built (the separate integrity fix in `src/cadrumo/application/modelo/export_accounts.py`), every Modelo 200 export refuses `REFUSED_MODELO_EXPORT_REQUIRED_RECORD_ABSENT` for page 002. The rows are taxpayer facts that hold across returns, so they need a persisted home, which is a profile schema decision.

## Considerations

- The design declares page 002 identically in the 2024 and 2025-y-siguientes export layouts: eight row families with fixed slot counts (`src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/export/0004-record-m200-page-002.toml` and the 0005-0009 records; the same files under `2025-y-siguientes`). The administrador family has 5 slots: nif, apellidos_nombre_razon_social, forma_juridica, codigo_provincia, domicilio_fiscal, representante. The other families are participacion_socio (6), representante_legal (3), secretario_consejo (1), participacion_directa (3), entidad_menor_dependiente (10), establecimiento_permanente (18) and socio_sicav_disolucion (5). The design has no cargo field.
- The typed rows already exist (`Modelo200ProjectionRows` and its row models). Only their source is missing.
- The profile already declares repeatable, effective-dated, sensitivity-tagged sections (`attribution_entity_socios`, `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:578`), so a new section needs no new storage mechanism.
- An empty family is ambiguous: a company that holds no participations and a filer who has not said so look the same. `2026-11-02-casilla-value-absence-adr` forbids letting padding or a default stand for a fact. Elsewhere the profile states absence through a tri-state field whose unanswered value blocks (`has_employees`, `colegio_concertado`).
- `2026-07-26-censal-profile-autofill-adr` notes that a required field on a repeatable section binds for no taxpayer when the section has no rows. Absence of a required family must therefore be checked at the family, not at the field.
- The persona states one unremunerated sole administrator and no holdings, so it needs no new figure.

## Considered options

- **Operator-supplied export-time rows (status quo of the typed snapshot).** Rejected: the rows hold across returns, and re-entering an administrator at every export invites drift. No door exists to supply them.
- **A separate encrypted register, as the Modelo 360 solicitud does (`2026-10-04-modelo-360-solicitud-custody-adr`).** Rejected: that register exists because the facts are per solicitud and may belong to a third party. Administradores and relations are facts of the taxpayer entity across periods, which is what the effective-dated profile expresses.
- **Profile sections, one per page-002 family, with a stated-none companion for each design-optional family.** Chosen.

## Constraints

1. **Fields and cardinality come only from the design.** Each family is a repeatable profile section whose fields are the design's fields for that family. Its row limit is the design's slot count, read from the export layout of the edition in force. The profile declares no limit of its own. A later edition that changes a family declares only that difference (delta keyed, PRIME 12:11).
2. **Administradores are required.** A Modelo 200 export with no administrador row refuses with a typed, served refusal whose door opens the profile section. It is never stated none. In each row F/J (forma_juridica) is required. RPTE (representante), domicilio fiscal and código provincia are filled only when the declarant is an IRNR contribuyente (casilla 00021 or 00046) and stay blank for a resident entity (manual sociedades 2024, lines 3838-3860, p. 98). They are conditional on that stored fact, not asked otherwise, and when the condition holds their absence blocks (condition h).
3. **Optional families need an explicit answer.** Every other family that could apply takes rows or an explicit "none", through a tri-state field per family on the same section (unanswered, none, has rows). Unanswered blocks the export with a served door. An empty family is never inferred.
3a. **Not applicable is served, not asked (condition g).** A family that the design or the law restricts to an entity form or regime which a stored profile fact already rules out (for example a SICAV dissolution for a sociedad limitada) is served as not applicable, with its deciding fact. The rule and its citation live in the registry.
3b. **B.2 participaciones en la declarante (condition j).** For a sociedad de responsabilidad limitada or a sociedad civil, B.2 carries at least one socio even below 5 %, and the percentages sum to 100 (manual sociedades 2024, lines 3986-3992 and 4013-4016, p. 102). "None" is refused for those forms. A sum other than 100 blocks with a served finding. The rule is keyed in the registry by entity form, with its citation.
4. **Privacy.** NIF, names and domicilio fiscal are declared `sensitivity = "identity"` and live only in encrypted profile custody. Fixtures, logs, stories and documentation carry synthetic values only.
5. **Schema version.** The schema takes the next version in landing order. A record of an earlier version that carries these paths is refused.
6. **Surfaces.** The sections are reachable through the existing profile row operations (CLI and operation registry), with served words in the four locales. Frontends render them through the served profile sections and author nothing.
7. **Mapping (condition i).** One mapper turns profile rows into `Modelo200ProjectionRows` by registry role and field name. There is no modelo-name branch outside the 200 producer. The mapping is round-trip tested through the real export for every admitted year.

## Implementation

We will add the eight page-002 families to the profile schema as effective-dated repeatable sections, with tri-state "none" fields for the seven optional families. The Modelo 200 producer profile (`_resolve_export_model_profile`) will read them at the period end of the work unit and build `Modelo200ProjectionRows`. A missing administrador or an unanswered family refuses with a typed refusal that has a door.

Proof: an export of the sociedad persona for every admitted year it covers, and a refusal test with no administrador. ACCEPTANCE maps the persona's `[[officers]]` block and states its holdings as none.

## Rationale

The rows are durable facts of the entity, so they belong in the effective-dated, encrypted profile, beside the other repeatable relations. The design remains the only authority on what each row holds and how many fit. A blocking door and explicit "none" keep identifying facts from being guessed and keep empty from meaning two things.

## Consequences

- Every Modelo 200 export needs the administradores and an answer for each optional family. Until those are given, a sociedad export refuses with a door instead of failing.
- The profile schema grows by eight sections. Profile migration, import and export carry them as other repeatable sections are carried.
- Families the persona never fills (establecimientos permanentes, SICAV) gain only a "none" answer, not a calculation.
