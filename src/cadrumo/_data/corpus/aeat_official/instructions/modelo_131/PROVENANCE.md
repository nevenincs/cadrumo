# Modelo 131 instructions corpus — provenance

## Documents

| File | Bytes | Modified | Type |
| ---- | ----- | -------- | ---- |
| `files/modelo-131-instrucciones.html` | 43854 | 2026-05-05 11:20 | AEAT Sede HTML — instrucciones page |
| `files/modelo-131-instrucciones-2026-late.html` | 44126 | 2026-10-03 04:57 UTC | AEAT Sede HTML — instrucciones page, September 2026 update |
| `files/modelo-131-presentacion-electronica-formulario.html` | 31838 | 2026-05-05 16:36 | AEAT Sede HTML — formulario page |
| `files/modelo-131-procedure.html` | 20659 | 2026-05-05 11:20 | AEAT Sede HTML — procedure landing |
| `files/modelo-131-recuperar-declaraciones-presentadas.html` | 13954 | 2026-05-05 16:36 | AEAT Sede HTML — recovery flow |
| `files/modelo-131-pdf-borrador-screenshot.png` | 100669 | 2026-05-05 11:52 | Screenshot — PDF preview |
| `files/modelo-131-vista-previa-button.png` | 17105 | 2026-05-05 11:52 | Screenshot — preview button |

## Source

- Authority: Agencia Tributaria (AEAT), Sede Electrónica.
- Source path: `sede.agenciatributaria.gob.es/Sede/` (per
  HTML `<base>` and embedded `<a href="/Sede/inicio.html">`).
- AEAT CMS ObjectId on the instrucciones page:
  `17924bffabab1710VgnVCM100000dc381e0aRCRD`.
- Page title (verbatim): "Agencia Tributaria: Instrucciones".
- The later instructions capture uses the same AEAT CMS ObjectId. Its
  recorded source URL is
  `https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/impuesto-sobre-renta-personas-fisicas/modelo-131-irpf______sionales-estimacion-objetiva-fraccionado_/instrucciones.html`.
  The source declaration in
  `registry/aeat/legal/modelo-131-2026-late-law-and-instructions.toml`
  records retrieval on 2026-10-03, 44126 bytes and SHA-256
  `a1f8370ac01d628910fd95ace2704c3e9e991b7265c943c0e4b4619dbf101b27`;
  the bundled file matches that byte count and digest.

## Last-update timestamps

- AEAT page footer "Página actualizada":
  `<time datetime="2026-04-01">01/abril/2026</time>` — AEAT
  published this page on 2026-04-01.
- Corpus filesystem mtime: 2026-05-05.
- The later capture's footer carries
  `<time datetime="2026-09-11">11/septiembre/2026</time>`.
  Its recorded retrieval date is 2026-10-03; this is a separate capture
  from the original May instructions and does not replace their history.

Implication: the corpus was fetched 2026-05-05 (or later) against
an AEAT page last published 2026-04-01. The 34-day delay between
AEAT publication and corpus capture is within the project's
corpus-freshness convention (re-fetch whenever a new clause is
quoted from the corpus).

## Verification

The carry-forward sentence that grounds the cap predicate
— "Casilla 11. Si en la casilla 10 anterior se
hubiera obtenido una cantidad positiva, se hará constar en la
casilla 11 el importe (sin signo) de los resultados negativos
que, en su caso, se hubieran obtenido en la casilla 15 de
cualquiera de las autoliquidaciones anteriores, modelo 131, del
mismo ejercicio y que no hubieran sido deducidos anteriormente,
teniendo en cuenta que en ningún caso podrá figurar en la
casilla 11 un importe superior a la cantidad positiva
consignada en la casilla 10." — is present verbatim in
`files/modelo-131-instrucciones.html` (the AEAT corpus
2026-05-05 capture of the 2026-04-01 publication).

The cap predicate (`cap_le_when_positive(["11", "10"])`)
declared on all 4 M131 revisions is therefore grounded against
the AEAT-published instructions verbatim at the corpus's
capture date.

## Re-fetch protocol

When AEAT updates Modelo 131 instructions (signalled by a change
to the page footer's "Página actualizada" datetime), the corpus
HTML files MUST be re-fetched from
`sede.agenciatributaria.gob.es/Sede/...` and this PROVENANCE.md
updated. The corpus carries no automatic re-fetch trigger; the
re-fetch is a manual action invoked when the project relies on a
new AEAT-published clause.
