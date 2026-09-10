# Modelo 840 — published form (formulario publicado)

The AEAT-published printed form for the Modelo 840 *Declaración del Impuesto
sobre Actividades Económicas* (alta, variación, baja).

## Why this file is load-bearing

This artefact is the **sole** grounding for the `label_pattern` values in the
Modelo 840 declaration-PDF extraction profile
(`registry/aeat/modelos/840/revisions/2003-y-siguientes/extraction_profiles/0001-declaracion-pdf.toml`),
which runs at `confidence = "strict"` with `failure_semantics = "fail_hard"`.

The approving order — Orden HAC/2572/2003, committed at
`corpus/normatives/html/orden-hac-2572-2003.html` — approves the form but does
**not** reproduce its numbered boxes: it contains zero occurrences of
`14 Ejercicio` or `15 Declaración de`. The printed form is therefore not a
convenience copy of the BOE text; it is the only committed evidence for the
casilla-number-prefixed labels the parser matches on. Deleting it would leave a
strict, fail-hard parser contract ungrounded.

## Source

| Field | Value |
| --- | --- |
| Canonical URL | <https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G323/mod840e_es_es.pdf> |
| Source page | <https://sede.agenciatributaria.gob.es/Sede/censos-nif-domicilio-fiscal/censos/iae-declaracion-ocios-efectos-iae-aeat_/descarga-modelo.html> |
| Procedure | G323 (IAE: alta, variación o baja) |
| Authority | AEAT (Sede Electrónica) |
| AEAT page last-updated | not published on the artefact URL |
| Corpus capture date | 2026-05-06 |

Byte counts and SHA-256 digests are recorded once, in `manifest.json`.

### URL provenance is reconstructed, not original

The capture commit (`d437d184c6`) recorded **no** source URL, so this artefact
sat in the corpus unpinned and unattributed. The URL above was recovered, not
copied from the original capture:

- The procedure code `G323` is established **in-repo** by
  `instructions/modelo_840/files/modelo-840-procedure.html`, which carries
  `data-proc="G323"` and an *Información → Descarga del modelo* link.
- The `static_files` path under that procedure code was recovered from the AEAT
  listing.
- Document identity was confirmed by **content correspondence** — the casilla
  labels `14 Ejercicio:` and `15 Declaración de:`, plus `Espacio reservado para
  la etiqueta identificativa`, `Clase de cuota`, and `Local afecto
  indirectamente`, all appear in the committed extraction.

Identity is therefore well grounded, but the recorded digest is that of the
**committed** artefact and has not been reconciled byte-for-byte against the
live URL. Re-verify on the next corpus refresh.

## Documents

| File | Role |
| --- | --- |
| `01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf` | the AEAT-published form (payload) |
| `01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf.extracted.json` | generated text sidecar (`dev.docs.preprocess`) |
| `01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf.extracted.md` | generated text sidecar (`dev.docs.preprocess`) |

The stored filename follows the `01-<modelo>-<listing-slug>-pdf.pdf` convention
that `dev/corpus/sync_aeat_record_design_corpus.py` derives from an AEAT page
listing title; AEAT's own filename (`mod840e_es_es.pdf`) is preserved in
`manifest.json` as `original_filename`.

## Dating

The form is the one approved by Orden HAC/2572/2003 and the registry revision
span is `2003-y-siguientes`. AEAT serves it from a stable, unversioned URL, so
the capture carries no era marker of its own.
