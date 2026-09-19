# BOE form-annex corpus — provenance

This directory holds two kinds of artefact, and confusing them is the thing this
record exists to prevent. Three files are **captures**: BOE PDFs downloaded
whole, where the bundled bytes are the bytes the publisher served. Nine are
**transcriptions**: plain text typed out from a BOE annex, where the bundled
bytes were produced here and no URL would ever serve them.

The registry rows for all twelve have the same shape — `sha256`, `bytes`,
`retrieved_at`, `source_url` — so a reader cannot tell the two apart from the
catalogue alone. That is what the tables below are for.

## Captures

The bundled bytes are what the address served.

| File | Bytes | Retrieved | Served from |
| ---- | ----- | --------- | ----------- |
| `boe-a-2003-1911-modelo-185-annex-i.pdf` | 290582 | 2026-08-26 | `boe.es/boe/dias/2003/01/30/pdfs/A03911-03920.pdf` |
| `boe-a-2023-17429-modelo-721-layout.pdf` | 294687 | 2026-06-28 | `boe.es/boe/dias/2023/07/29/pdfs/BOE-A-2023-17429.pdf` |
| `boe-a-2024-27528-modelo-721-layout-amendment.pdf` | 827110 | 2026-06-28 | `boe.es/boe/dias/2024/12/31/pdfs/BOE-A-2024-27528.pdf` |

The 2003 modelo 185 PDF looks authored to
`classify_normative_corpus_provenance`, which reads a file's own bytes for a
`BOE-A-…` identifier or BOE structural markup and finds neither. It is
nonetheless a genuine capture: the PDF carries `/Producer (BOE)` and
`/CreationDate (D:20030130000000)`, the day BOE published it. The identifier
scheme that classifier looks for postdates the document. That classifier's
subject is the text a legal reference cites, not these source files, so nothing
consults it here — the mismatch is recorded only so the next reader who runs it
out of curiosity does not read the answer as a finding.

## Transcriptions

**The bundled bytes were typed here, not downloaded.** Each file is the visible
text of one modelo's form as that BOE disposición publishes it, and its
`sha256` in the sources catalogue pins the transcription against later edits —
it does not and cannot verify the transcription against the original. Checking
one means opening the address in the last column and reading it.

They exist because the formula declarations cite them: a `required_text`
citation verifies a formula's stated arithmetic against the form's own printed
caption, and for these modelos that caption exists only inside a scanned image.
Nothing else in the corpus carries it as text.

| File | Modelo | Bytes | Transcribed from |
| ---- | ------ | ----- | ---------------- |
| `boe-a-1999-22309-modelo-194-annex-text.txt` | 194 | 1370 | scanned annex `datos/imagenes/disp/1999/277/22309_7966157_image71.png` |
| `boe-a-1999-22372-modelo-188-annex-text.txt` | 188 | 1246 | scanned annex `datos/imagenes/disp/1999/278/22372_7962537_image24.png` |
| `boe-a-2007-20485-modelo-126-annex-text.txt` | 126 | 1152 | scanned annex `datos/imagenes/disp/2007/286/20485_14167491_image7.png` |
| `boe-a-2007-20485-modelo-128-annex-text.txt` | 128 | 703 | scanned annex `datos/imagenes/disp/2007/286/20485_14167491_image9.png` |
| `boe-a-2008-18497-modelo-296-annex-text.txt` | 296 | 839 | scanned annex `datos/imagenes/disp/2008/277/18497_11330375_image3.png` — **withdrawn by BOE, see below** |
| `boe-a-2014-9225-modelo-187-annex-text.txt` | 187 | 1092 | scanned annex `datos/imagenes/disp/2014/220/09225_4930.png` |
| `boe-a-2018-17997-modelo-117-annex-text.txt` | 117 | 1405 | scanned annex `datos/imagenes/disp/2018/314/17997_6094.png` |
| `boe-a-2007-20485-modelo-123-annex-text.txt` | 123 | 1569 | the disposición's own PDF, `boe.es/eli/es/o/2007/11/23/eha3435/dof/spa/pdf` |
| `boe-a-2024-1772-modelo-123-annex-text.txt` | 123 | 1437 | the disposición's own PDF, `boe.es/boe/dias/2024/01/31/pdfs/BOE-A-2024-1772.pdf` |

### Two derivations, and why they read differently

The last column splits the table in two, and the split is visible in the bytes.

The seven **scanned-annex** transcriptions were typed from a raster image, so
they are ASCII-folded: `Declaracion`, `regularizacion`, `Numero`. Nothing was
extracted, so no accent survived to be preserved.

The two **modelo 123** transcriptions came from a PDF whose text layer is
readable, so they keep their diacritics: `Autoliquidación`, `regularización`,
`Número`. The `required_text` citations that check them are accented to match.

This is a real difference in how the text was obtained, not drift to be
normalised away. Folding the accented pair would silently break the citations
that verify modelo 123's formulas; adding accents to the other seven would
assert a fidelity to the scan that typing from an image does not have.

### Modelo 117 is attributed to 2018, not 2007

`boe-a-2018-17997-modelo-117-annex-text.txt` was named `boe-a-2007-20485-…`
until 2026-09-19, which contradicted every other field on its row — the image it
was typed from is from BOE-A-2018-17997, and the row declares
`published_at = 2018-12-29`, `applies_from = 2019-01-01`. The text settles it:
the transcription carries the boxes 04/05/06 for *transmisiones de derechos de
suscripción*, which Orden HAC/1417/2018 introduced and the 2007 form does not
have. The file was renamed to the disposición it actually comes from; the bytes
are unchanged.

Orden EHA/3435/2007 remains modelo 117's layout authority and is still cited as
`boe-modelo-117-form-layout`. The 2018 orden amends it; it does not replace it.

### The modelo 296 annex image is gone

`datos/imagenes/disp/2008/277/18497_11330375_image3.png` answers 404. The
transcription is unaffected — it was made while the image was served — but it
can no longer be checked against its original at that address, and re-deriving
it would mean finding the annex elsewhere in BOE-A-2008-18497.

The withdrawal is recorded in `dev/corpus/source_url_liveness.py`, which probes
every registered address and fails when the withdrawal census stops matching
what the publishers answer.

## Re-deriving a transcription

Open the address in the table, read the annex, and retype it. Then update the
`sha256` and `bytes` on the owning row in the sources catalogue, and check that
every `required_text` citation naming that row still matches — a caption retyped
with different spacing or different accents will pass its digest pin and fail
its citations, which is the failure this file's diacritic note exists to warn
about.
