# Modelo 145 — published form (formulario publicado)

The AEAT-published printed form for the Modelo 145 *Comunicación de datos al
pagador*. This is the form facsimile the taxpayer hands to the payer; it is
**not** a filing artefact (Modelo 145 is never presented to the AEAT) and it is
**not** a record design. It is cited by the registry as
`official_source_guidance` evidence for the form's box inventory and for the
regulatory anchor printed on its face (artículo 88 RD 439/2007).

## Source

| Field | Value |
| --- | --- |
| Canonical URL | <https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G603/mod145_es_es.pdf> |
| Source page | <https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/retenciones-ingresos-cuenta/obligaciones-retenedor/modelo-145.html> |
| Authority | AEAT (Sede Electrónica) |
| AEAT page last-updated | not published on the artefact URL — see *Dating* below |
| Corpus capture date | 2026-05-14 |

Per-file URLs, byte counts, and SHA-256 digests are recorded once, in
`manifest.json`. They are not restated here.

## Documents

| File | Role |
| --- | --- |
| `mod145_es_es.pdf` | the AEAT-published form (payload) |
| `mod145_es_es.pdf.extracted.json` | generated text sidecar (`dev.docs.preprocess`) |
| `mod145_es_es.pdf.extracted.md` | generated text sidecar (`dev.docs.preprocess`) |

## Locale

The `_es_es` token is AEAT's own upload filename, preserved verbatim as
upstream provenance (the same convention as `dr145v20.pdf` in
`disenos_registro/`). It is **not** a project locale-dispatch axis: the
declared locale is `es-ES` in `manifest.json`, and nothing in the product
selects a corpus artefact by locale. AEAT also publishes this form in ca/gl/eu
/va; those variants are **not** captured. Do not read the filename as evidence
that a locale axis exists.

## Dating

AEAT serves this form from a stable, unversioned URL as "the current form", so
neither the URL nor the filename carries a version or an era. The only internal
lower bound the document offers is its data-protection footer, which cites
*Ley Orgánica 3/2018, de 5 de diciembre* — so this capture is at or after
2018-12-05 and **must not** be treated as evidence for a pre-2019 filing
period. The registry source pins that bound as `applies_from`.

This is a real residual gap, recorded rather than papered over: a future
recapture replaces the file in place and the era can only be re-derived from
the document's own citations. If AEAT reissues the form with different boxes,
the superseded capture must be retained under its own directory rather than
overwritten, or the evidence for previously grounded work is destroyed.
