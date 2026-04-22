# AEAT PDFs — canonical vocabulary

Kent encounters six distinct AEAT-produced PDFs in his filing lifecycle. Each has its own Spanish name, its own stage, its own carrying of casilla values, and — for four of the six — its own import backend inside this tool. This page is the one-stop reference so every contributor uses the same words for the same documents.

The vocabulary is locked by [ADR `pdf-taxonomy`](../../.vault/adr/2026-04-21-pdf-taxonomy-adr.md) (EPIC #305, cluster A).

## Justificante de presentación

**What it is**: the receipt AEAT emails or surfaces on Sede after Kent submits a filing. 1–2 pages. Contains modelo, período, CSV, totales (*total a ingresar* / *total a devolver*), timestamp, and NIF. **Does NOT contain per-casilla values.**

**Where Kent gets it**: email attachment, or Sede → Mis expedientes → download after filing.

**Imported by**: `aeat filing import --from-justificante <PATH>` (shipped via issue #271). Produces a metadata scaffold `FilingDraft` — every casilla `EMPTY` — and a companion `SubmittedFiling` record usable as the baseline for amendment flows (#93, #234, #235).

## Declaración (copia de la declaración)

**What it is**: the full filed copy. Multi-page. Contains the complete per-casilla breakdown — every value Kent put on the form, AEAT-stamped with a CSV at the foot. The authoritative post-filing record.

**Where Kent gets it**: downloaded from Sede after submission, or exported by the AEAT form applet at submission time.

**Imported by**: `aeat filing import --from-declaracion <PATH>` (cluster D — in progress; lands per-modelo under EPIC #305).

## Borrador

**What it is**: the pre-filing draft AEAT computes for Kent. Primarily a Renta (Modelo 100) artefact; AEAT publishes it via Portal Renta with Kent's rentas, retenciones, deducciones pre-populated from datos fiscales. Multi-page. **Contains per-casilla values** but no CSV (it hasn't been filed).

**Where Kent gets it**: Portal Renta (cert-gated), or the public Renta Web Open simulator for any synthetic input (no cert).

**Imported by**: `aeat filing import --from-borrador <PATH>` (cluster F — summary-block MVP).

## Predeclaración / simulación

**What it is**: a non-binding simulation. Typically from Renta Web Open or the Modelo 100 simulators. Structure mirrors the declaración. No CSV.

**Where Kent gets it**: Renta Web Open (anonymous), or the Portal Renta pre-submission flow.

**Imported by**: `aeat filing import --from-predeclaracion <PATH>` (cluster F MVP shares the same extractor as the borrador — structure is equivalent for summary-block purposes).

## Datos fiscales

**What it is**: the informational statements AEAT has on Kent's file — retenciones por pagador, intereses bancarios, rentas inmobiliarias, cotizaciones autónomo. Multi-page narrative PDF; lists *inputs* to compute casilla values, not the casillas themselves.

**Where Kent gets it**: Portal Renta → Datos fiscales; Sede → Mis datos.

**Not an import source.** Datos fiscales is a candidate future source for the `aeat filing build` input wizard (pre-fill Kent's known retenciones into a draft), but it does not map to a filing via PDF extraction because it does not carry casillas. See EPIC #305 umbrella research for rationale.

## Datos personales / identificativos

**What it is**: NIF / address / régimen snapshot. Identity boilerplate AEAT surfaces on Kent's profile page.

**Not an import source.** Kent's identity lives in `AutonomoProfile` (`aeat.deadlines` module) and is managed via `aeat profile` commands, not ingested from PDFs.

## At-a-glance

| Spanish name | Carries casillas? | Carries CSV? | Import flag |
| --- | --- | --- | --- |
| justificante de presentación | ❌ (totales only) | ✅ | `--from-justificante` (shipped) |
| declaración | ✅ | ✅ | `--from-declaracion` (cluster D) |
| borrador | ✅ (pre-populated) | ❌ | `--from-borrador` (cluster F) |
| predeclaración | ✅ | ❌ | `--from-predeclaracion` (cluster F) |
| datos fiscales | ❌ (inputs, not outputs) | ❌ | — (not an import source) |
| datos personales | ❌ | ❌ | — (identity, not filing data) |

## Why we keep the Spanish module names

Per project mandate, Spanish is the authoritative AEAT terminology baseline. Module names mirror the Spanish originals: `aeat.justificante`, `aeat.declaracion`, `aeat.borrador`, `aeat.predeclaracion`. No anglicisation of concepts that AEAT itself names. CLI flags follow the same rule.

## See also

- [ADR — PDF taxonomy](../../.vault/adr/2026-04-21-pdf-taxonomy-adr.md)
- [ADR — real-PDF fixture corpus](../../.vault/adr/2026-04-21-real-pdf-fixture-corpus-adr.md)
- [ADR — declaración extractor](../../.vault/adr/2026-04-21-declaracion-extractor-adr.md)
- [ADR — calc verification](../../.vault/adr/2026-04-21-calc-verification-adr.md)
- [ADR — Modelo 100 Renta MVP](../../.vault/adr/2026-04-21-modelo-100-renta-adr.md)
- [Umbrella research — real-PDF import](../../.vault/research/2026-04-21-real-pdf-import-umbrella-research.md)
