# Modelo 349 instructions corpus — provenance

## Documents

| File | Bytes | Modified | Type |
| ---- | ----- | -------- | ---- |
| `files/instr_mod_349.pdf` | 620231 | 2026-08-07 22:40 | AEAT Sede PDF — instrucciones (fetched original) |
| `files/instr_mod_349.txt` | 69284 | 2026-08-07 22:40 | Text extraction of the PDF above |
| `files/instr_mod_349.pdf.extracted.json` | 74499 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/instr_mod_349.pdf.extracted.md` | 69094 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/modelo-349-plazos-presentacion.html` | 6470 | 2026-08-25 07:29 | AEAT Sede HTML — plazos de presentación |
| `files/modelo-349-procedure.html` | 46458 | 2026-08-07 22:40 | AEAT Sede HTML — procedure landing |

## Source

- Authority: Agencia Tributaria (AEAT), Sede Electrónica.
- `instr_mod_349.pdf` — the fetched original behind registry source
  `aeat-modelo-349-instructions`, whose `source_url` is
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/GI28/instr_mod_349.pdf`,
  retrieved 2026-05-26. sha256
  `36859c125b4aef4c4428471a573d3b717029ea92783b347b934a9fb05bbc4fa2`.
  That registry entry pins its `.txt` text extraction rather than the PDF
  bytes, so the PDF itself had no enforced record until this document; the
  URL it names is unambiguously this file.
- `instr_mod_349.txt` — enrolled as `aeat-modelo-349-instructions`, sha256
  `735dc0b1be1bed8997bd77a97fb0cb54e54d77a083082f5b72cf6aa236717adf`,
  69284 bytes, retrieved 2026-05-26.
- `modelo-349-procedure.html` — enrolled as `aeat-modelo-349-procedure`,
  sha256 `ad3bc47a0ca9846bec8789cdaea867b504d3774205e3993cea52a39040f8811e`,
  46458 bytes, retrieved 2026-05-05. AEAT CMS ObjectId
  `bba1c43f826ad610VgnVCM100000dc381e0aRCRD`. Page title (verbatim):
  "Agencia Tributaria: Modelo 349. Declaración Informativa. Declaración
  recapitulativa de operaciones intracomunitarias."
- `modelo-349-plazos-presentacion.html` — enrolled as
  `aeat-modelo-349-plazos-presentacion`, sha256
  `dd8b78e97a307d83c34dd8261a35cc195142baeb60ada450af1b5840888b1a2c`,
  6470 bytes, retrieved 2026-08-25. AEAT CMS ObjectId
  `370c0313f9351710VgnVCM100000dc381e0aRCRD`. Page title (verbatim):
  "Agencia Tributaria: Plazos de presentación".

The registry entries remain the authoritative pins; the rows above restate
them so this directory's record is complete in one place.

## Last-update timestamps

- `modelo-349-procedure.html` footer "Página actualizada":
  `<time datetime="2020-12-30">`.
- `modelo-349-plazos-presentacion.html` footer "Página actualizada":
  `<time datetime="2026-07-08">`.
- Corpus capture (filesystem mtime): 2026-08-07, except
  `modelo-349-plazos-presentacion.html` at 2026-08-25.

The instrucciones PDF carries no in-band page timestamp; its authority is
the retrieval date and digest recorded above.

## Verification

`instr_mod_349.pdf` pages 8-9 supply the verbatim label text reproduced by
the modelo 349 justificante fixtures, and its text extraction carries the
GB/XI ordinary and rectification clauses asserted by the modelo 349
registry tests. Re-fetch whenever a new clause is quoted from it.
