# Modelo 036 instructions corpus — provenance

## Documents

| File | Bytes | Captured | Type |
| ---- | ----- | -------- | ---- |
| `aeat-modelo-036-procedure.html` | 36079 | 2026-07-21 | AEAT Sede HTML — procedure landing |
| `files/anexo-03-instrucciones-modelo-036.html` | 10007 | 2026-07-21 | AEAT Sede HTML — anexo 3 index |
| `files/instrucciones-cumplimentacion-pagina-1.html` | 17271 | 2026-07-21 | AEAT Sede HTML — cumplimentación page 1 |
| `files/presentacion-papel-modelo-036.html` | 31296 | 2026-07-21 | AEAT Sede HTML — paper presentation |
| `files/Folleto_Censos.pdf` | 245570 | 2026-07-21 | AEAT PDF — folleto censos (+ extracted `.json` / `.md`) |
| `files/anexo-03-instrucciones-cumplimentacion-pagina-4.html` | 10967 | 2026-08-07 | AEAT Sede HTML — **carries the tipo-de-actividad code table** |
| `files/capitulo-04-actividades-economicas-locales-actividad.html` | 13893 | 2026-08-07 | AEAT Sede HTML — same table, plus the epígrafe-IAE scope sentence |

SHA-256 of the two 2026-08-07 captures:

    f64a0abeb8516ba9681616f9b76d6954cbf391dc1a9b261352c4fee81b31e3a5  anexo-03-instrucciones-cumplimentacion-pagina-4.html
    a1c9cb40b1dbe78150421d5dd4575e1e12b0bae91c919bcabb60b5b8f012be39  capitulo-04-actividades-economicas-locales-actividad.html

## Source

- Authority: Agencia Tributaria (AEAT), Sede Electrónica.
- Base: `sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/guia-practica-cumplimentacion-modelo-censal-036/`
- The two 2026-08-07 captures came from, respectively,
  `anexos/anexo-03-instrucciones-modelo-036/cumplimentacion-modelo/pagina-4.html`
  and
  `capitulo-04-actividades-economicas-locales/cumplimentacion-declaracion-actividades-economicas-locales/actividad.html`.
- AEAT page footer "Página actualizada" on both: `<time datetime="2026-03-26">26/marzo/2026</time>`.

## Why the two 2026-08-07 captures were added

The Modelo 036 **diseño de registro** names field 403 only as `Tabla`, without
enumerating the table. Sweeps of the bundled diseño corpus for the values
therefore came back empty, and the AEAT diseño index page confirms the negative
directly: it links exactly one file for Modelo 036, `DR036v43.xlsx`, with no
table annex.

The table is published in the **instrucciones**, not with the diseño. These two
pages are where it lives. They are independent pages on the sede and carry the
table identically, which is why both are bundled rather than one: a later
re-fetch that finds them disagreeing is a signal worth having.

## The table, verbatim

Introduced by `Código/Tipo de actividad: se cumplimentará de acuerdo con las
siguientes tablas.`

*Actividades económicas que forman parte del hecho imponible del Impuesto sobre
Actividades Económicas:*

| Código | Tipo de actividad |
| ------ | ----------------- |
| `A01` | Arrendadores de Bienes inmuebles |
| `A02` | Ganadería independiente |
| `A03` | Resto empresariales |
| `A04` | Artísticas y Deportivas |
| `A05` | Profesionales |

*Actividades económicas que no forman parte del hecho imponible del Impuesto
sobre Actividades Económicas:*

| Código | Tipo de actividad |
| ------ | ----------------- |
| `B01` | Agrícola |
| `B02` | Ganadera |
| `B03` | Forestal |
| `B04` | Producción de mejillón |
| `B05` | Pesquera |

## A second clause worth recording

`capitulo-04-...-actividad.html` also states, of the epígrafe/sección IAE field:

> Solamente se cumplimentará esta casilla en el supuesto de que la actividad
> forme parte del hecho imponible del impuesto, es decir, solo para las
> actividades comprendidas dentro de los códigos de actividad A01, A02, A03,
> A04 y A05.

That is AEAT stating directly that the IAE epígrafe is absent for every
`B`-series filer — the agrarian ones. It is the authority behind the corpus
observation that `iae_epigraph` is systematically empty for exactly the filers
an agrarian discriminator would need to identify.

## Re-fetch protocol

Both pages were published 2026-03-26 and captured 2026-08-07. When AEAT updates
them (signalled by a change to the footer's "Página actualizada" datetime), the
HTML MUST be re-fetched and this file updated, including the SHA-256 values. The
corpus carries no automatic re-fetch trigger.
