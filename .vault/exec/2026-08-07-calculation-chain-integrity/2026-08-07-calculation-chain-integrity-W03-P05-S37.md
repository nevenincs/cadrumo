---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a9056f95ba5fea665f9da451079c35ea6fa0a2c506b57144a1c77939427b0e43'
step_id: 'S37'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S37

## Outcome

**Done. The artefact is bundled.** The gate was never really a fetch gate — it was a discovery gate wearing a fetch gate's clothes, and the thing nobody could find was not missing, it was filed somewhere else.

## Why every sweep came back empty

The Modelo 036 diseño de registro names field 403 only as `Tabla` and enumerates nothing. Sweeping the bundled diseño corpus for the values therefore found nothing, and the natural next move — re-fetch the diseño — was checked and confirms the negative directly: the AEAT diseño index page links exactly one file for Modelo 036, `DR036v43.xlsx`, with no table annex.

The table is published in the **instrucciones**, not with the diseño. That is the whole finding.

## What was bundled

Two AEAT sede pages, both under the guía práctica for the modelo censal 036:

    anexos/anexo-03-instrucciones-modelo-036/cumplimentacion-modelo/pagina-4.html
    capitulo-04-actividades-economicas-locales/cumplimentacion-declaracion-actividades-economicas-locales/actividad.html

Both were bundled rather than one. They are independent pages that carry the table identically today, so a later re-fetch finding them disagreeing is a signal worth being able to see.

Ten codes, introduced by `Código/Tipo de actividad: se cumplimentará de acuerdo con las siguientes tablas.`

- **Sujetas a IAE:** `A01` Arrendadores de Bienes inmuebles, `A02` Ganadería independiente, `A03` Resto empresariales, `A04` Artísticas y Deportivas, `A05` Profesionales
- **No sujetas a IAE:** `B01` Agrícola, `B02` Ganadera, `B03` Forestal, `B04` Producción de mejillón, `B05` Pesquera

`PROVENANCE.md` follows the `modelo_131` convention: per-file table, sha256 for the two new captures, source URLs, the AEAT `2026-03-26` publication stamp, and the re-fetch protocol.

## A second clause that came free

The capitulo-04 page also says, of the epígrafe/sección IAE field, that it is filled *solo para las actividades comprendidas dentro de los códigos de actividad A01, A02, A03, A04 y A05*.

That is AEAT stating directly that the IAE epígrafe is absent for every B-series filer — the agrarian ones. `W03.P04` had observed empirically that `iae_epigraph` is systematically empty for exactly those filers; this is the authority behind the observation, and it closes off the obvious fallback discriminator before anyone spends time on it.

## Note on the scope field

The row named `_data/corpus/aeat_official/disenos_registro/modelo_036/`, which is where the artefact was assumed to belong. It landed under `instructions/modelo_036/` instead, beside the folleto and the other M036 instruction captures, because that is what it is.
