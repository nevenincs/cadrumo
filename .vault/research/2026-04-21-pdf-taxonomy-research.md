---
tags:
  - "#research"
  - "#pdf-taxonomy"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-12-justificante-parser-adr]]"
  - "[[2026-04-20-pdf-import-adr]]"
---

# pdf-taxonomy research: which AEAT PDFs carry what, and which ones we can actually import

## Problem

`aeat.domain.justificante` reads one specific document (the *justificante de presentación* — receipt). The `#271` import command is named "import past filing from justificante PDF" but a justificante does not carry casilla values, so the feature can only reconstruct a metadata scaffold. The user's concern is that real calculation-verified import requires targeting a **different** AEAT document entirely.

Before scoping extractors (cluster D), fixture corpora (cluster C), or schema completion (cluster B), we need a clear, code-grounded taxonomy of the PDFs AEAT produces and an explicit map of "which PDF is the import target for which flow."

## AEAT PDF taxonomy (observed from AEAT Sede electrónica + Manual práctico)

Every AEAT-produced PDF a taxpayer encounters falls into one of six classes. The axis that matters for us is **"does it carry the per-casilla numeric breakdown?"**.

| PDF class | ES name | Stage | Carries casillas? | Carries CSV / metadata? | Notes |
| --- | --- | --- | --- | --- | --- |
| **Receipt** | *Justificante de presentación* | Post-filing | ❌ (totales only) | ✅ | 1–2 pages. Legal proof of filing. What `aeat.domain.justificante` currently parses. |
| **Filing copy** | *Declaración / Copia de la declaración / Ejemplar para el declarante* | Post-filing | ✅ (full) | ✅ (CSV printed at foot) | Multi-page. One section per modelo block. The target for calc-verified import. |
| **Draft** | *Borrador* | Pre-filing | ✅ (pre-populated) | ❌ (no CSV — unfiled) | Multi-page, Renta-specific primarily; downloadable from Portal Renta. Carries AEAT's pre-computed draft. |
| **Pre-declaration** | *Predeclaración / Simulación* | Pre-filing | ✅ | ❌ | Non-binding preview. Used by Modelo 100 simulators. Structure matches declaración. |
| **Fiscal data** | *Datos fiscales* | Pre-filing | ❌ (enumerates inputs, not casillas) | ❌ | Informational statements AEAT has on file (retenciones, rentas del trabajo, intereses…). **Inputs to compute casillas, not casillas themselves.** |
| **Personal data** | *Datos personales / identificativos* | Pre-filing | ❌ | ❌ | NIF / address / régimen snapshot. Identity boilerplate. |

Key inference:

- **Receipt** (what `#271` reads) → only good for **scaffold + amendment baseline**.
- **Filing copy** + **Draft** + **Pre-declaration** → the only PDFs that actually let us reconstruct casilla values.
- **Fiscal data** is a different semantic layer (inputs, not outputs) and could later feed the `aeat filing build` wizard but is **not** a filing-import source.

The `#271` feature is therefore correctly scoped to its name — the naming confusion is that the project talks about "importing past filings" but only ever reads the receipt. A separate, complementary feature is needed to import the **filing copy**.

## Technical characteristics per PDF class

Relevant for cluster D (extractor design):

| PDF class | Typical pages | Layout | Font-embedding | XFA? | Coordinate-stability across years |
| --- | --- | --- | --- | --- | --- |
| Receipt (modelo 130, 303, 111, 115, 180…) | 1–2 | Simple label:value lines | TTF, embedded | No (modern) | High |
| Receipt (modelo 100) | 2–3 | Similar, slightly denser | TTF | No | High |
| Filing copy (modelo 130, 303, 111, 115, 180…) | 2–4 | Form-layout with boxed casillas | TTF | **Sometimes** (2018 and older) | Medium — AEAT revises template graphics yearly but casilla IDs are stable |
| Filing copy (modelo 100) | 10–30+ | Multi-page form with Anexos | TTF | **Historically yes** (pre-2020); now mostly static | Low — layout drifts every year; casilla IDs mostly stable across years |
| Borrador (modelo 100) | 10–30+ | Similar to filing copy | TTF | No (modern Renta Web output) | Low |
| Datos fiscales | 3–8 | Narrative + tables | TTF | No | Medium |

**XFA risk**: `pdfplumber` does not read XFA form fields — it sees the rendered page only. For older Modelo 100 PDFs that embed XFA overlay data with the real casilla values inside, `pdfplumber.extract_text` will show the rendered static layer only; the form-field values are not in the extracted text stream. Options: (a) scope MVP to modern (≥ 2020) Renta PDFs only, (b) add `pypdf` as a secondary parser to pull `/AcroForm` / XFA fields when present, (c) rely on layout-regex fallback even for XFA PDFs (usually works for visual rendering).

## How each class surfaces to Kent

| Origin | How Kent gets it | Reliably accessible without cert auth? |
| --- | --- | --- |
| Receipt | Downloaded by Kent from Sede after filing (email or portal) | ✅ (Kent saved it himself) |
| Filing copy | Downloaded by Kent from Sede after filing OR exported by the AEAT form applet | ✅ (Kent saved it himself) |
| Borrador | Downloaded from Portal Renta; cert-gated in the portal | ✅ (Kent already downloaded it) |
| Datos fiscales | Portal Renta; cert-gated | ✅ (Kent already downloaded it) |

All four are **Kent-local** once Kent has saved them. None require the tool to hit AEAT.

## Evidence from the repo

- `.vault/adr/2026-04-12-justificante-parser-adr.md` — scopes `aeat.domain.justificante` to the receipt only.
- `.vault/adr/2026-04-20-pdf-import-adr.md` §2.7 — explicitly records that line-level casillas are not in the receipt and emits a warning.
- `src/aeat/domain/justificante/_schema.py` — `Justificante` fields: `csv`, `modelo`, `period`, `ejercicio`, `presentation_id`, `presented_at`, `tax_id`, `total_a_ingresar`, `total_a_devolver`, `verification_url`, `source_pdf_path`, `source_pdf_sha256`, `parsed_at`. No casilla tuple. Consistent with receipt-only scope.
- `src/aeat/application/filing/_import.py` — wraps the receipt parser; draft casillas fall through to `FilingValueKind.EMPTY` via the builder's `_materialise_literal`.
- No code anywhere reads a *declaración*, *borrador*, *predeclaración*, *datos fiscales*, or *datos personales* PDF today.

## Naming drift in existing code

- Module name `aeat.domain.justificante` is correct for the receipt.
- Command name `aeat filing import --from-justificante` is correct for the receipt.
- EPIC `#233` is titled **"Kent imports a past filing from its justificante PDF"** — this conflates receipt import with filing import and is where the user's concern surfaces linguistically. The EPIC's child issues need to distinguish "receipt import" (#271 — shipped) from "filing-copy import" (new — not yet scoped).

## Proposed terminology (to formalise in the ADR)

| Project term | ES source | Meaning |
| --- | --- | --- |
| `JustificanteReceipt` / `aeat.domain.justificante` | *justificante de presentación* | Post-filing receipt. Metadata + totals only. (As today.) |
| `FilingCopy` / `aeat.adapters.inbound.declaracion` (new) | *copia de la declaración* | Post-filing full filing PDF. Casilla-complete. |
| `FilingDraftPdf` / `aeat.adapters.inbound.borrador` (new) | *borrador* | Pre-filing draft (primarily Renta). Casilla-complete, un-CSV-stamped. |
| `FilingPreview` / `aeat.predeclaracion` (new) | *predeclaración / simulación* | Pre-filing simulation. Casilla-complete, non-binding. |
| `FiscalDataStatement` / `aeat.datos_fiscales` (new) | *datos fiscales* | Informational statements used as **inputs** to Modelo 100. Not a filing-import source. |

The word "justificante" stays locked to the receipt. "Declaración", "borrador", "predeclaración", "datos fiscales" each get their own module when they get implemented.

## Cross-cluster implications

- **Cluster B (schema completeness)**: a casilla-complete schema is prerequisite for extracting any of {declaración, borrador, predeclaración}. Schema completeness does **not** affect receipt parsing.
- **Cluster C (fixture corpus)**: the fixture axis must track *both* `(modelo, año)` and *PDF class*. One receipt per modelo/year is not enough; we need one filing copy and one borrador per modelo/year for the classes that support them.
- **Cluster D (extractor)**: one extractor contract per PDF class. Receipt extractor already exists. Filing-copy extractor is the main build in cluster D.
- **Cluster E (verification)**: verification only makes sense over PDF classes that carry casillas (filing copy / borrador / predeclaración). Applied to a receipt, `audit_against` has nothing to compare.
- **Cluster F (Modelo 100)**: the receipt / filing-copy / borrador distinction is sharpest for Renta. Receipt is trivial; filing copy is the declaración; borrador is a separate PDF with different layout quirks. Cluster F inherits this split.

## Open questions (to close in the ADR)

1. Do we rename `aeat.domain.justificante` to `aeat.receipt` / `aeat.justificante_receipt` or leave the Spanish as the project convention? Policy: Spanish is the authoritative AEAT terminology (per project mandate), so **keep** `aeat.domain.justificante` and introduce siblings `aeat.adapters.inbound.declaracion`, `aeat.adapters.inbound.borrador`, etc.
2. Is `aeat filing import --from-justificante` kept, renamed, or supplemented? Recommendation: **supplement** — add `--from-declaracion`, `--from-borrador` flags; keep `--from-justificante` for the amendment-baseline path.
3. Does cluster E's verification apply across all three casilla-carrying classes uniformly? Yes — all three produce the same `(casilla_id, printed_value)` tuple shape, so one verification pipeline fits all.
