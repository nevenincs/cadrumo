---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-08-05'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:b3728196967dd61d952297a6f74cb203adce2c9e5dd81a9b9c068f4b1b6cc774'
related: []
---

# `schema-hardening` research: `AEIP anexo-A event-keyed continuity`

Modelo 100 anexo A carries the deductions for *acontecimientos de excepcional interés
público* plus the general LIS deduction roster. It is the corpus's renumbering
minefield and the single largest blocker on continuity grounding: a batch pass over
the legal-refs-only tranche had to park 593 Modelo 100 chains because their
`semantic_role` is shared by more than one casilla in the same revision, and the
anexo-A family is the core of that set.

The evidence below establishes two facts that together rule out every mechanical
keying scheme: a casilla id does not identify an event across years, and an event
title does not identify an event across years either. The two failures point in
opposite directions, so no single derivation is safe, and the scheme has to be a
curated registry rather than a slug function.

## Findings

### The shared-role problem is far wider than anexo A

The batch pass measured 149 distinct `semantic_role` values shared by two or more
casillas within one revision, blocking 593 chains. Anexo A is the largest cluster but
not the only one: the top blocking roles are `irpf_toma_datos_declarante_selector`
(44 chains), `irpf_anexo_b_importe_anual_satisfecho` (24),
`irpf_anexo_b_deduccion_inversion_importe` (16), `irpf_eo_agr_indice` (16),
`irpf_anexo_a_aeip_aplicado` (12), `irpf_deduccion_inversion_empresarial_entidad_nif`
(12). Any scheme scoped to AEIP event programs alone leaves most of the 593 parked.

### The anexo-A family: 451 occurrences, two columns, 177 candidate chains

Across the six Modelo 100 revisions (2020 through 2025) the roles prefixed
`irpf_anexo_a_aeip` cover 451 casilla occurrences, split between exactly two columns —
`irpf_anexo_a_aeip_aplicado` (315 occurrences) and `irpf_anexo_a_aeip_aplicado_flag`
(136). Keying by (program title, column) yields 177 candidate chains, of which 113
span more than one revision and 64 appear in a single revision. The 113 are precisely
the chains continuity exists to express, and no id- or role-keyed scheme can reach
them.

The roles are not exclusively AEIP events: the same roles carry the general LIS roster
rows (`Deducciones acogidas al régimen general de la Ley del Impuesto sobre
Sociedades`, `Actividades de investigación y desarrollo e innovación tecnológica (art.
35º de la LIS)`, `Creación de empleo para trabajadores con discapacidad (art. 38º de
la LIS)`). A scheme named `irpf.aeip.*` would mis-describe those rows.

### Failure one: an id holds different events across years

43 casilla ids carry a genuinely different program across revisions, and 31 held more
than one distinct quoted event title. The worked example from the earlier brief
reproduces exactly: id `0757` is "175 Aniversario de la construcción del Gran Teatre
del Liceu" in 2020, "Gran Premio de España de Fórmula 1" in 2021 through 2023, and
"Primavera Sound, created in Barcelona" in 2025. Id `0760` held "Centenario Federación
Aragonesa de Fútbol", "VIII Centenario de la Universidad de Salamanca" and "Año Tàpies.
Cien años del nacimiento del artista Antoni Tàpies" in different years; id `0761` held
"Eduardo Chillida 100 años", "20 Aniversario de la Reapertura del Gran Teatre" and
"Plan 2030 de Apoyo al Deporte de Base". Stamping one `continuidad_id` per id would
assert that three unrelated event programs are one legal concept.

### Failure two: an event's title drifts, so a title slug splits one chain

The inverse hazard is real and would be invisible to a reviewer checking only for
collisions. Id `0764` carries "España País Invitado de Honor en la Feria del Libro de
Fráncfort **en 2021**" in the 2020 and 2021 revisions and "...**en 2022**" in the 2022
revision. That is one event program whose published title embeds a drifting year
token; a slug derived from the title would mint two chains for it and silently break
the continuity it was meant to record. Separately, normalising wording and punctuation
collapsed 45 text-varying ids to 43, so 2 were pure rewording (`art. 37º del TRLIS`
versus `art. 37 del TRLIS`; "producciones cinematográficas y series audiovisuales"
versus "producciones cinematográficas, series audiovisuales y espectáculos en vivo").
Title text is therefore unstable in both directions: same title different event, and
same event different title.

### Consequence for the scheme

A derived slug cannot be trusted on its own. The shape the evidence supports is a
curated event registry: an explicit table mapping a stable event key to its
`{revision: casilla_id}` occurrences, authored once against the anexo-A roster and
reviewed, with the label used as *discovery* input rather than as the key. The chain
id would then be `irpf-aeip-<event-key>-<column>` with `column` drawn from the two
observed values. It must be a FLAT segment: `ContinuidadId` still permits dots, but
the localization cascade makes the chain id a segment of the shared locale key, and
`encode_modelo_locale_segment` base32-encodes anything that is not a plain
`^[A-Za-z0-9_-]+$` segment. The damage is silent and shows up only as an unreadable
catalogue key, which is why `dev/registry/aeip` declaring `CHAIN_PREFIX =
"irpf.aeip."` has to be flattened before that planner grounds anything. 137 distinct
quoted event titles exist in the corpus, so the curated table is on the order of 140
rows plus the non-event LIS roster rows, which need a separate non-AEIP name. Event
titles run long, so the 128-character bound is a real constraint on the key, not a
formality.

### Churn and volume

Event windows open and close every year, so this family generates `retired` records at
scale — 64 of the 177 candidate chains appear in one revision only and would retire at
their next boundary. That argues for generating the scaffolding from the curated table
rather than hand-authoring, with the table itself being the reviewed artifact. A
generator is worth proposing; it is out of scope to build here.

### What was not investigated

Whether the AEAT anexo-A roster is published in a machine-readable form that would give
event keys directly, which would remove the curation cost entirely and should be
checked before anyone hand-authors 140 rows. Also unexamined: whether the `aplicado`
and `aplicado_flag` columns always co-occur, which determines whether the column
segment is needed in the key at all.

## Sources

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/casillas/`
- `src/cadrumo/domain/calculations/registry/_schema_base.py` (the `ContinuidadId` constraint)
- `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py`
- commit `2788477897` (the batch pass whose parked buckets this quantifies)
- commit `bff1bc9f0c` (the casilla-order gate; label resolution now runs through the loader)
