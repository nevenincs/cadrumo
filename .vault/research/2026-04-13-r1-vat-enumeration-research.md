---
name: r1-vat-enumeration-research
description: Research notes for the R-1 VAT (IVA) enumeration + Ley 37/1992 codification feature.
type: research
tags:
  - "#research"
  - "#r1-vat-enumeration"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
  - "[[2026-04-13-r1-vat-enumeration-plan]]"
---

# r1-vat-enumeration research

## scope

Track B (Transaction Data Pipeline) step R-1: give the financial-input
subsystem a strictly-typed, hand-reviewed enumeration of Spanish VAT
(IVA) situations and a minimal EU rate table, each codified against
specific articles of **Ley 37/1992, del Impuesto sobre el Valor
Añadido** (BOE-A-1992-28740).

This substrate is what downstream categorisation (#77), provider
detection (#73), and the TDP classifier layers will read when they
need to tag a transaction with its VAT treatment.

## ley 37/1992 structure

Ley 37/1992 is organised into nine titles. The articles the R-1
substrate cites most heavily are:

- **Título preliminar — Naturaleza y ámbito de aplicación** (Arts. 1–3):
  defines the territorial scope (TAI, Canarias/Ceuta/Melilla excluded).
- **Título I — Delimitación del hecho imponible** (Arts. 4–9):
  `Art. 4` — hecho imponible for entregas de bienes y prestaciones de
  servicios. `Art. 7` — operaciones no sujetas. `Art. 8` — concepto de
  entrega de bienes.
- **Adquisiciones intracomunitarias** (Arts. 13–16): `Art. 13` — hecho
  imponible de AIB. `Art. 14` — operaciones no sujetas.
- **Importaciones** (Arts. 17–19).
- **Título II — Exenciones** (Arts. 20–67):
  `Art. 20` — exenciones en operaciones interiores (sanidad, enseñanza,
  financieras, inmobiliarias, etc.). `Art. 21` — exenciones a la
  exportación. `Art. 22` — exenciones en operaciones asimiladas a las
  exportaciones. `Art. 24`/`Art. 25` — entregas intracomunitarias
  exentas. `Art. 27` — exenciones en importaciones.
- **Título III — Lugar de realización del hecho imponible** (Arts.
  68–74): reglas de localización de entregas y servicios.
- **Título IV — Devengo** (Arts. 75–77).
- **Título V — Base imponible** (Arts. 78–83).
- **Título VI — Sujetos pasivos** (Arts. 84–89): `Art. 84` — inversión
  del sujeto pasivo (reverse charge).
- **Título VII — El tipo impositivo** (Arts. 90–91):
  `Art. 90` — tipo general (21 %). `Art. 91` — tipos reducidos
  (10 %, 4 %) con el detalle de los bienes y servicios que los
  disfrutan en `Art. 91.Uno` y `Art. 91.Dos`.
- **Título VIII — Deducciones y devoluciones** (Arts. 92–119 bis).
- **Título IX — Regímenes especiales** (Arts. 120–163):
  `Art. 122–134` — régimen simplificado.
  `Art. 135–139` — régimen de bienes usados, objetos de arte (REBU).
  `Art. 141–147` — régimen especial de las agencias de viajes.
  `Art. 148–163` — recargo de equivalencia.
- **Título X — Obligaciones de los sujetos pasivos** (Arts. 164 ss.):
  `Art. 164` — obligaciones formales (facturas, libros, declaraciones
  liquidaciones).

## 2025 rates in spain

- **General (21 %)** — `Art. 90.Uno`. Aplica salvo que el bien o
  servicio esté en el listado del Art. 91.
- **Reducido (10 %)** — `Art. 91.Uno`. Cubre alimentación (excluyendo
  los productos del 4 %), hostelería, transporte de viajeros, vivienda
  nueva, etc.
- **Súper-reducido (4 %)** — `Art. 91.Dos`. Pan común, harinas panificables,
  leche, queso, huevos, frutas, verduras y hortalizas, libros, medicamentos,
  prótesis, vivienda de protección oficial en régimen especial, etc.
- **0 %** — transitorio en bienes de primera necesidad (2023–2024) y
  entregas intracomunitarias exentas. El 2025 ya vuelve al régimen
  ordinario para los alimentos pero se mantiene el 0 % conceptual
  para las entregas EXENTAS (Art. 24).

## eu rate landscape (2025)

Codified from the European Commission's "VAT rates applied in the
Member States of the European Union" summary, retrieval_date =
2026-04-13. Highlights of standard (general) rates:

- AT 20, BE 21, BG 20, HR 25, CY 19, CZ 21, DK 25, EE 22, FI 25.5,
  FR 20, DE 19, GR 24, HU 27, IE 23, IT 22, LV 21, LT 21, LU 17, MT 18,
  NL 21, PL 23, PT 23, RO 19, SK 23, SI 22, ES 21, SE 25.

We do not need to enumerate every reduced/super-reduced rate for every
member state — the substrate's job is to let callers *look up* a rate
shape, not to replicate the whole EU fiscal directory. ES and DE get
the full reduced/super-reduced/zero expansion, the remaining 25
states get at least their standard rate. The table is hand-sourced
and carries its `effective_from` / `effective_until` for rate-history
support.

## special regimes relevant to autónomo r-1

- **Régimen simplificado** (Arts. 122–134) — módulos; compatibility
  with recargo de equivalencia only for retail activities.
- **Recargo de equivalencia** (Arts. 148–163) — mandatory for natural
  persons selling retail. Rates 5.2 / 1.4 / 0.5 on top of the standard
  VAT rate. The supplier charges the *autónomo* the recargo and the
  autónomo has no right to file a Modelo 303.
- **Inversión del sujeto pasivo (reverse charge)** — Art. 84. The main
  drivers for autónomo R-1 flows are intra-community acquisitions
  (Art. 13 + Art. 84.Uno.2º.a) and certain services received from
  non-established providers.
- **Operaciones intracomunitarias**:
  - Supply (exportación a otro estado miembro con NIF-VAT válido):
    Art. 25 — exenta, se declara en Modelo 349.
  - Acquisition (compra desde otro estado miembro con NIF-VAT válido):
    Art. 13 + reverse charge — se autorrepercute y se deduce en
    Modelo 303, se declara en Modelo 349.
  - Triangulación: tres estados miembros, el intermediario no tributa
    en destino; Art. 26.tres.
- **Exportaciones a terceros países** — Art. 21 — exentas, se declaran
  como ventas y no generan IVA.
- **Importaciones de terceros países** — Art. 17–19 + Art. 86, el IVA
  lo liquida la Aduana (Modelo K — DUA); para autónomos con inversión
  del sujeto pasivo se declara en Modelo 303 casillas específicas.

## manual práctico iva 2025

`corpus/manuals/iva/2025/manifest.json` carries the PDF manifest but
**no extracted structured content**. The manual's structured sections
will land via a follow-up extraction feature; R-1 deliberately does
not depend on them. The corpus loader for VAT rules must gracefully
fall back to the hand-coded `VAT_CATALOGUE_2025` when no structured
`{year}.json` file exists in the VAT catalogue root. The fallback
must be logged (INFO level) so operators notice if they expected a
disk load.

## invariants we must preserve

1. **Pydantic mandate** — every record is a strict frozen pydantic v2
   model (`_StrictFrozen` base). No dataclasses, no bare dicts.
2. **Trilingual contract** — every `Translatable` field carries the
   authoritative Spanish (`es`) key, enforced by a model validator.
3. **Closed catalogue = StrEnum** — `VATCategory`, `VATRateKind`,
   `EUMemberState`, `CitationSource`.
4. **Citations are mandatory** — every `VATRegulation` carries ≥1
   `Citation` with non-empty `quoted_text_es` pointing at an article
   of Ley 37/1992 (or a Directive 2006/112/EC article for the
   EU-wide categories).
5. **≥30 rules with ≥1 citation each** — the TDP Step R-1 contract
   requires at least 30 codified rules; this feature packs multiple
   citations per VATRegulation so the total citation count across the
   16 regulations is ≥32.
6. **Source of truth** — `pyproject.toml [project].version` and the
   normatives corpus for Ley 37/1992 remain authoritative for the
   legal act itself; the VAT substrate cites articles by number and
   does not re-copy the statutory text beyond what the quoted_text_es
   field requires for auditability.

## open questions / out of scope

- Recargo de equivalencia rate table per commodity class — out of
  scope for R-1 (belongs to a future R-2 categorisation pass).
- REBU (Art. 135) — out of scope; autónomo flows do not usually
  require it.
- Full intra-community triangulation flows — codified as a single
  `VATCategory.INTRA_COMMUNITY_TRIANGULATION` regulation citing
  Art. 26.tres, with the routing detail deferred.
