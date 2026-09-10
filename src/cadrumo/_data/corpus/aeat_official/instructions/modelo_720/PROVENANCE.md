# Modelo 720 instructions corpus — provenance

## Documents

| File | Bytes | Modified | Type |
| ---- | ----- | -------- | ---- |
| `files/modelo-720-aeat-dr.pdf` | 612620 | 2026-08-07 22:40 | AEAT Sede PDF — diseño de registro |
| `files/modelo-720-aeat-dr.pdf.extracted.json` | 43651 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/modelo-720-aeat-dr.pdf.extracted.md` | 40087 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/modelo-720-procedure.html` | 40144 | 2026-08-31 06:48 | AEAT Sede HTML — procedure landing |

## Source

- Authority: Agencia Tributaria (AEAT), Sede Electrónica.
- `modelo-720-aeat-dr.pdf` — the published diseño de registro, retrieved
  2026-05-27 from
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_Resto_Mod/archivos/modelo_720.pdf`.
  sha256 `ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7`.
  URL and retrieval date are recorded verbatim in the modelo 720
  `2013-y-siguientes` extraction-profile grounding note; this document
  promotes them out of a code comment into the enforced corpus record.
- `modelo-720-procedure.html` — enrolled in the registry as
  `aeat-modelo-720-procedure`, which pins sha256
  `4855e7816565a93ace64e718a53a2681db927372ad3811a1cc6d63b92588241a`,
  40144 bytes, retrieved 2026-05-06. The registry entry remains the
  authoritative pin; the row above restates it.
- AEAT CMS ObjectId on the procedure page:
  `3613c43f826ad610VgnVCM100000dc381e0aRCRD`.
- Page title (verbatim): "Agencia Tributaria: Modelo 720. Declaración
  Informativa. Declaración sobre bienes y derechos situados en el
  extranjero".

## Last-update timestamps

- `modelo-720-procedure.html` footer "Página actualizada":
  `<time datetime="2023-10-31">` — AEAT published this page 2023-10-31.
- Corpus capture (filesystem mtime): 2026-08-07 for the diseño de registro
  and its derivatives, 2026-08-31 for the procedure page.

The diseño de registro carries no in-band page timestamp; its authority is
the retrieval date and digest recorded above.

## Verification

`modelo-720-aeat-dr.pdf` record-type-1 positions 5-8 (EJERCICIO) ground the
`decl.ejercicio` label pattern of the `modelo-720-declaracion-pdf`
extraction profile. Re-fetch whenever a new clause is quoted from it.
