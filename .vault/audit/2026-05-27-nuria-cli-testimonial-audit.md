---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-olivia-cli-testimonial-audit]]"
  - "[[2026-05-27-mateo-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-17 Núria Vallès editorial cooperativa atribución de rentas M184 Catalan`

## Scope

Seventeenth testimonial round, Núria Vallès Puigdomènech —
Catalan, 39, Girona resident. Co-founded a sociedad civil sin
personalidad jurídica fiscal (Catalan-language children's books
editorial) with two friends. Régimen de atribución de rentas
(Art. 8 + 88-90 LIRPF). Society total benefit €34k, Núria's
share 40% (€13,600). Plus part-time librarian salary €18k.
Quota autónomos €4,200/year.

Exercises Modelo 184 (informativa anual entidades atribución),
attribution_entity profile axis, M184 → M100 attribution binding,
and Catalan locale parity across the registry. None previously
tested.

## Findings

### CRITICAL — M184 multi-row member declaration mechanism inaccessible

`aeat app modelo bindings list --modelo 184 --year 2024 --period 0A`
returns 4 bindings for `atribucion_member` rows (nif, name, share,
base-assigned) but all are `ledger source` — no `--binding KEY=VALUE`
direct entry path. Indexed syntax attempts rejected:
- `modelo-184-member-row-nif[0]=...` → "no és un BindingId vàlid"
- `modelo-184-member-row-nif:0=...` → "unknown registry binding ids"
- Repeated same key → overwrites, doesn't accumulate.

A sociedad with 3 sòcies has no CLI mechanism to declare all
three. The intended pathway (`atribucion_member` ledger-source)
exists conceptually but has no documented creation/import verb.
M184 stays in `borrador` permanent — verifier blocks closure
without member rows.

### CRITICAL — M184 tipo2 text-typed casillas have no input channel

Verifier requires casillas `tipo2.clave` (renta type: A=capital
mobiliario, C=capital inmobiliario, D=actividades económicas),
`tipo2.subclave`, `tipo2.miembro-nif`, `tipo2.renta-atribuible-
importe`. All are `data_type = text` and post-#174 guard
correctly rejects `--casilla` decimal input. But also NOT
listed as valid bindings: `--binding tipo2.clave=D` → "unknown
registry binding ids".

Verifier marks them blocking with legal_refs (orden-hap-2250-2015:
art-3, ley-35-2006:art-88). No input channel exists. M184 cannot
reach `verified` state.

### HIGH — M184 → M100 attribution binding does not exist

`aeat app modelo bindings list --modelo 100` returns 6 bindings:
M111/M115/M123/M193 retenciones + EDS modalidad + CCAA. NO
`renta-2024-modelo-184-atribucion-de-rentas`. Each sòcia must
manually transcribe her attributed share into M100 casilla
0102 (rendimientos atribuidos). Risk of transcription error
between society's M184 and three individual M100s — closes
the informativa → personal automatic loop missing.

### MEDIUM — Quota autónomos deduction path not accessible via CLI

`--casilla "0180=4200"` rejected (calculated casilla). `--casilla
"0096=..."` not recognised. Only visible path: classify the
quota payment in ledger and rely on `actividad_economica`
binding aggregation — but the circuit is not documented. Núria
loses €4,200 deduction unless she discovers the ledger path
externally.

### MEDIUM — `sociedad_civil_mercantil` nomenclature confusing

`--entity-type legal_entity --legal-entity-form sociedad_civil_
mercantil` is the IS-route option (Ley 27/2014 post-2016
SCs with objeto mercantil). Users with a sociedad civil sin
personalidad jurídica fiscal (atribución régimen) need
`--entity-type attribution_entity` — but no help message
guides this. A user trying `legal_entity + sociedad_civil_*`
gets a confusing error or wrong route.

### MEDIUM — Registry casilla labels remain in Spanish despite `--output-language ca`

CLI chassis (commands, errors, operational messages, work_create
confirmations) is in genuine Catalan. But the `key_figure`
label field stays Spanish: `"Base imponible general"` instead
of `"Base imposable general"`. Same for `"Clave del tipo de
renta atribuida"` instead of Catalan equivalent. The registry
TOML `label` field is single-language; not multi-locale.

Distinct from chassis localisation — registry label translation
is a structural shape decision. Document the boundary or extend
the registry schema to support translated labels.

### LOW — `attribution_entity` entity-type EXISTS — POSITIVE confirmation

`--entity-type attribution_entity` is a first-class option,
distinct from `legal_entity`. M200 work_create on attribution
profile correctly refuses with legally-grounded message:
"Una entidad en régimen de atribución de rentas... no presenta
autoliquidación de cuota propia: no tributa por el Impuesto
sobre Sociedades ni por el IRPF. La renta se atribuye a cada
socio... La obligación propia de la entidad es informativa
(Modelo 184)." Excellent.

### LOW — NIF check-digit calculator missing

CLI correctly rejects wrong-letter NIF/CIF with Catalan message
naming expected vs received digit. Helpful but user without the
NIF must guess. A `aeat config compute-tax-id-checksum E17000019`
verb would help.

### LOW — M184 single revision `2015-y-siguientes`

Only one revision declared. Technically correct (M184 form
unchanged since 2015) but explanation lacking when user sees
revision rejection list.

### LOW — `overview status` lacks `--output-language`

Uses profile default. Cannot override per-call.

## Recommendations

Priority order:

1. **F1 + F2 (CRITICAL — unblock M184):** add multi-row
   declaration mechanism. Either a `--member NIF=X,SHARE=Y,
   CLAVE=Z,IMPORTE=W` repeatable flag, OR a `aeat app modelo
   work socio add WORK_UNIT_ID --nif --share --clave --importe`
   subcommand. Without this, M184 functionally exists but cannot
   reach `verified` for any real sociedad.

2. **F3 (HIGH — informativa → personal loop):** add binding
   `renta-2024-modelo-184-atribucion-de-rentas` to M100 registry
   that pulls the sòcia's attributed share from her sociedad's
   M184. Mirror the existing M111/M123 previous_filing pattern.

3. **F4 (MEDIUM):** document quota autónomos deduction circuit
   in `--help` text. Either via ledger classification or a
   binding alias. Currently undiscoverable.

4. **F5 (MEDIUM):** add help message on `--entity-type
   legal_entity --legal-entity-form sociedad_civil_*` pointing
   to `--entity-type attribution_entity` for SC sin personalidad
   jurídica.

5. **F6 (MEDIUM):** decide on registry label localisation policy.
   Either extend schema to multi-locale labels OR document the
   chassis/registry boundary explicitly.

The positive structural finding: `attribution_entity` is a
first-class entity type and the IS/atribución legal distinction
is correctly enforced. The remaining gaps are around the
multi-row M184 input mechanism and the M184↔M100 attribution
binding. Both are tractable extensions of existing patterns
rather than missing structural foundations.
