# Modelo 369 instructions corpus — provenance

## Documents

| File | Bytes | Modified | Type |
| ---- | ----- | -------- | ---- |
| `files/1-declarante.html` | 7993 | 2026-08-07 22:40 | AEAT Sede HTML — manual section 1 |
| `files/2-ejercicio-periodo.html` | 11006 | 2026-08-07 22:40 | AEAT Sede HTML — manual section 2 |
| `files/8-resultado-autoliquidacion.html` | 9407 | 2026-08-07 22:40 | AEAT Sede HTML — manual section 8 |
| `files/9-tipo-pago.html` | 12416 | 2026-08-07 22:40 | AEAT Sede HTML — manual section 9 |
| `files/Descripcion_PresentacionFichero369_v1.pdf` | 702350 | 2026-08-07 22:40 | AEAT Sede PDF — diseño de registro / presentación de fichero |
| `files/Descripcion_PresentacionFichero369_v1.pdf.extracted.json` | 6830 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/Descripcion_PresentacionFichero369_v1.pdf.extracted.md` | 5844 | 2026-08-07 22:40 | Derivative — parser cache, regenerated from the PDF above |
| `files/modelo-369-procedure.html` | 20824 | 2026-08-07 22:40 | AEAT Sede HTML — procedure landing |

## Source

- Authority: Agencia Tributaria (AEAT), Sede Electrónica.
- The four numbered HTML files are consecutive sections of one AEAT online
  manual, "Presentación régimen de la Unión", under
  `sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/modelo-369/presentacion-regimen-union/`.

  **Recorded verbatim** — the URL of section 2 is quoted, with fetch date
  2026-05-27, in the modelo 369 `esquema-union` extraction-profile grounding
  note. **Derived, not recorded** — sections 1, 8 and 9 are attributed to the
  same manual directory by the manual's own section numbering and by their
  page titles, which are the numbered section headings verbatim. No captured
  record states their URLs, and no retrieval date was logged for them; the
  in-band AEAT identifiers below are their primary pin.

  | File | AEAT CMS ObjectId | Page title (verbatim) | sha256 |
  | ---- | ----------------- | --------------------- | ------ |
  | `1-declarante.html` | `f4f0af0e378ca710VgnVCM100000dc381e0aRCRD` | "Agencia Tributaria: 1. Declarante" | `899f0e122f4341ad77d856cc1c667b6c29ce4ed9271f43797c75ab26816e44ff` |
  | `2-ejercicio-periodo.html` | `3cf0af0e378ca710VgnVCM100000dc381e0aRCRD` | "Agencia Tributaria: 2. Ejercicio y periodo" | `44f5efce2467737e61e2ba459aad20f98540f5eb3b5fe494a2685d4ba15ec2c6` |
  | `8-resultado-autoliquidacion.html` | `2241af0e378ca710VgnVCM100000dc381e0aRCRD` | "Agencia Tributaria: 8. Resultado de la autoliquidación por EM de consumo" | `2b0f41680ed6f4275675fcd6168a748c44c571aee0ebcdbd1f2a10355d1489a9` |
  | `9-tipo-pago.html` | `0941af0e378ca710VgnVCM100000dc381e0aRCRD` | "Agencia Tributaria: 9. Tipo de Pago" | `bba48bf193b403e2085b6f7faa9e9dc0828e27ac5a5a033841e8d1da325068dc` |

- `Descripcion_PresentacionFichero369_v1.pdf` — the presentación-de-fichero
  description accompanying diseño de registro DR369e21 (Versión 1.1),
  retrieved 2026-05-27. sha256
  `521fb8e9918b77555be781434006d560bbec28d30318ff158096ecca0e9ed56d`.
  The companion workbook URL
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos_21/DR369e21.xlsx`
  and the fetch date are recorded verbatim in the same extraction-profile
  grounding note; the direct URL of this PDF is not.
- `modelo-369-procedure.html` — enrolled in the registry as
  `aeat-modelo-369-procedure`, which pins sha256
  `5c776cc0640147af7a937963fe7cf88a53fb67e3b465924f742f7ba9273be1b6`,
  20824 bytes, retrieved 2026-05-06. AEAT CMS ObjectId
  `c300a546efaa1710VgnVCM100000dc381e0aRCRD`. Page title (verbatim):
  "Agencia Tributaria: Modelo 369. Declaraciones de IVA del régimen One Stop
  Shop (OSS)". The registry entry remains the authoritative pin.

## Last-update timestamps

AEAT footer "Página actualizada", read from each committed page:

| File | Página actualizada |
| ---- | ------------------ |
| `1-declarante.html` | 2025-07-29 |
| `2-ejercicio-periodo.html` | 2025-07-28 |
| `8-resultado-autoliquidacion.html` | 2025-07-28 |
| `9-tipo-pago.html` | 2026-05-19 |
| `modelo-369-procedure.html` | 2021-06-18 |

Corpus capture (filesystem mtime): 2026-08-07 for every file in this
directory. The PDF carries no in-band page timestamp; its authority is the
retrieval date and digest recorded above.

## Verification

Section 2's headings "2. Ejercicio y periodo" and its instruction text
ground the `decl.ejercicio` and `decl.periodo` label patterns of the
`esquema-union` extraction profile, cross-checked against sheet T36904 Un
of DR369e21. Sections 1, 8 and 9 are captured context and are not currently
cited by any extraction profile. Re-fetch whenever a new clause is quoted,
and record the URL and retrieval date at capture time so the derived
attribution above can be replaced with a recorded one.
