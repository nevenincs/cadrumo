# Modelo 232 instructions corpus — provenance

## Documents

| File | Bytes | Modified | Type |
| ---- | ----- | -------- | ---- |
| `files/Instrucciones_Modelo_232.pdf` | 376447 | 2026-08-07 22:40 | AEAT PDF — instrucciones de cumplimentación |
| `files/Instrucciones_Modelo_232.txt` | 20820 | 2026-08-07 22:40 | Text extraction of the PDF above |
| `files/Instrucciones_Modelo_232.pdf.extracted.json` | 22467 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/Instrucciones_Modelo_232.pdf.extracted.md` | 20770 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/modelo-232-procedure.html` | 35923 | 2026-08-07 22:40 | AEAT Sede HTML — procedure landing |

## Source

- Authority: Agencia Tributaria (AEAT).
- `Instrucciones_Modelo_232.pdf` — sha256
  `44a7606d2e5be723416c441ca8824e31fbfdf35af3554dceef2da4185e1a2a0c`.
  In-band document metadata, read verbatim from the committed bytes:
  `/Title (Intrucciones Modelo 232)` (AEAT's own spelling),
  `/Creator (Acrobat PDFMaker 24 para Word)`,
  `/Producer (Adobe PDF Library 24.5.96)`,
  `/CreationDate D:20251031120306+01'00'`,
  `/ModDate D:20251031120404+01'00'`.
  Page 1 opens "MODELO 232 / INSTRUCCIONES DE CUMPLIMENTACIÓN /
  CUESTIONES GENERALES", confirming the document's identity.
- `Instrucciones_Modelo_232.txt` — sha256
  `f29879561ce6a669638dfa8b7c1b5143f6f648478eaf933dd4f0ab6e93794075`,
  a text extraction of the PDF above, not an independently sourced document.
- `modelo-232-procedure.html` — enrolled in the registry as
  `aeat-modelo-232-procedure`, which pins sha256
  `33e413e281e789a4080228d8fb97df1209cd0b633df4d691808079168ad5f31b`,
  35923 bytes, retrieved 2026-05-05, from
  `https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI43.shtml`.
  The registry entry remains the authoritative pin.

**Not recorded** — no captured record states the instrucciones PDF's
retrieval URL or the date it was fetched into this corpus. Its AEAT
authorship date (2025-10-31, from `/CreationDate`) is the date AEAT produced
the file, which is not the same fact as a corpus retrieval date, and the two
are deliberately not conflated here.

## Last-update timestamps

- `Instrucciones_Modelo_232.pdf` in-band `/ModDate`: 2025-10-31 — the date
  AEAT last wrote the file, not a page-publication timestamp.
- Corpus capture (filesystem mtime): 2026-08-07.

## Verification

Known defect in the committed text extraction: `Instrucciones_Modelo_232.txt`
interleaves characters from the PDF's two-column layout (page 1 reads
"OEBstLaIrGánA DoOblSi gAa dPoRsE SaE pNreTsAeRn t ar"). It is unsuitable for
verbatim clause quotation in its current form; quote from the PDF, or
regenerate the extraction column-aware, before grounding any calculation in
it. Record the URL and retrieval date at the next re-fetch so the PDF can be
promoted to a hash-pinned registry source.
