---
tags:
  - '#research'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:5955980de4722951df1796c7ad7040cc173baeadc19b11136308f7a48e564c91'
related: []
---

# `issue-620-external-pdf-signal` research: `authority adjudication`

Issue #620 initially classified ten externally downloaded PDFs as wholly
unverified. That vocabulary loses a result the evidence can establish: every
candidate is a modified third-party sample, but its visual form lineage can be
adjudicated independently against official BOE or AEAT publications. The
remaining design question is how to preserve artifact authenticity, official
layout ancestry, and registry applicability as separate claims.

## Findings

### Artifact authenticity and form ancestry are different facts

All ten digest-pinned files visibly identify themselves as FiscalBot examples
without legal validity and contain the sample receipt number `1234567890`.
Their hashes, sizes, page selections, form overlays, and producer histories do
not equal the official artifacts used for comparison. They therefore cannot be
represented as official AEAT or BOE bytes. This is a positive third-party
artifact verdict, not an unresolved provenance state.

The official-base question has independent evidence. Ordered text, box
topology, affine coordinate fits, and normalized rendering comparisons establish
that each candidate derives from a named official form. The fillable member of
each pair renders as the same visual base as its plain member while adding empty
AcroForm fields. Rewritten PDFs prevent recovery of an exact intermediate AEAT
preview byte, but that limitation does not erase the demonstrated official-form
lineage.

### M130 and M131 derive from amended official forms and remain structurally current

The original 2007 annexes contain only 14 M130 and 12 M131 numbered boxes and
are not the candidates' base. Orden HAP/258/2015 replaced those annexes with the
19-box M130 and 15-box M131 forms reproduced by the candidates and by the
consolidated Orden EHA/672/2007. Ordered layout comparison produced text
similarities of 0.9345 for M130 and 0.9415 for M131, with the distinctive
section and calculation order preserved. Each plain/fillable pair has an exact
96-dpi render match. The registry exposes the same 19-box M130 topology in
`2019-y-siguientes` and 15-box M131 topology through its current 2026 revision.

AEAT's current paper-presentation guidance for both modelos describes a PDF
generated after online completion and validation rather than publishing a
static blank as filing authority. The candidates therefore provide verified
current-layout derivatives, not official filing artifacts or populated-value
evidence.

### M303 derives from the official 2024-late/2025 family but is obsolete for 2026

The repository's official AEAT manual annex
`src/cadrumo/tests/fixtures/manual_annexes/303/source-Cap_9_303_es_es.pdf`
has SHA-256
`fd42e40bd4ddb6f737ce8007e6e72b101465292abcf76a9d2ba01c791539491d`.
Candidate pages map to its form pages 1, 3, and 6 with 96.4--100% coordinate
word agreement and 0.37--0.73% raster delta. The candidates contain the
post-September-2024 rectification structure with boxes 108, 109, and 111, so
they align with registry revisions `2024-desde-09-y-3t` and `2025`. The 2026
official instructions add box 112 and revise the result chain; neither
candidate is current for registry revision `2026-y-siguientes`.

### M036 is a verified historical 2024 derivative, not a current-registry form

Candidate pages 1, 4, 5, and 6 map to physical pages 19, 24, 25, and 26 of
BOE-A-2023-26632 Annex I. Ordered token matches range from 401/424 to 658/665;
affine x/y fits have R-squared 0.99999--1.00000 and median residuals no greater
than 0.32 points horizontally and 0.05 points vertically. The 2025 replacement
in BOE-A-2025-410 changed the form. The registry deliberately starts at
`2025-02-03-y-siguientes` and pins DR036v43, whose SHA-256 is
`791479fbf9e905faf1e43fa0bfbff974d5edaf85d198495892fa8446a1da2ebd`.
Consequently the candidates have verified historical lineage but no applicable
current registry revision.

### M349 is a verified historical physical-form derivative, not current filing authority

The candidates preserve the section and box order of BOE-A-2010-5098 Annex I.
Its summary-page comparison has 261 ordered matching tokens with affine
R-squared 0.952/0.996; an interior page has 165 matches with R-squared
0.977/0.994. The current registry revision `2020-y-siguientes` points to the
electronic fixed-width 500-record contract, including the pinned DR with
SHA-256
`874db49c9aff4d9c024bdee52f869123a9815c09272a0066cf81421ace1a8335`.
The consolidated order makes current M349 presentation electronic-only. The
2010 visual ancestry is verified, while current registry applicability is not.

### The registry must constrain every applicability claim

The existing cross-model matrix selects 2026 snapshots for every candidate.
That is defensible for parser-adversarial execution but overstates authority
alignment for M303, M036, and M349. A durable contract needs an explicit
registry status: applicable current revision, applicable historical revision,
or historical layout with no applicable authored registry revision. Tests can
still pass historical bytes through production parsing primitives, but their
outcome must not be reported as current-form verification.

### The evidence favors a three-axis adjudication contract

Keeping a single `unverified` authority flag discards the official-form lineage
proved above. Promoting candidates to official specimens would falsely conflate
derivation with publication and would contradict their own disclaimers.
Rejecting the files would discard useful independent parser evidence. The
evidence favors a contract that records separately: third-party artifact
authenticity, verified official-base derivation with a pinned source and
measurement, and registry revision applicability. The follow-up ADR must settle
that vocabulary and whether official comparison bytes or only their digests and
derived measurements are retained.

## Sources

- Candidate contract and sidecars: `src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py`, `src/cadrumo/tests/fixtures/external_layout_candidates/{036,130,131,303,349}/*.json`.
- Registry revisions: `src/cadrumo/_data/registry/aeat/modelos/{036,130,131,303,349}/`.
- M130/M131 original order: https://www.boe.es/boe/dias/2007/03/22/pdfs/A12417-12434.pdf
- M130/M131 amended forms: https://www.boe.es/boe/dias/2015/02/19/pdfs/BOE-A-2015-1656.pdf
- M130/M131 consolidated order: https://www.boe.es/buscar/pdf/2007/BOE-A-2007-6032-consolidado.pdf
- M130 AEAT paper guidance: https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-130/presentacion-papel-modelo-130.html
- M131 AEAT paper guidance: https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-131/presentacion-papel-mediante-formulario-modelo-131.html
- M303 official 2024 annex: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/IVA_2024/Imagenes/Cap_9_303_es_es.pdf
- M303 official 2025 annex: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/IVA_2025/Imagenes/Cap_9_303_es_es.pdf
- M303 official 2026 instructions: https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2026.html
- M303 2026 order: https://www.boe.es/eli/es/o/2026/01/22/hac27
- M036 official 2024 form: https://www.boe.es/boe/dias/2023/12/29/pdfs/BOE-A-2023-26632.pdf
- M036 current 2025 form: https://www.boe.es/boe/dias/2025/01/09/pdfs/BOE-A-2025-410.pdf
- M036 current design record: https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_01_99/archivos/DR036v43.xlsx
- M036 AEAT paper guidance: https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-036/presentacion-papel-modelo-036.html
- M349 official historical form: https://boe.es/boe/dias/2010/03/29/pdfs/BOE-A-2010-5098.pdf
- M349 consolidated order: https://www.boe.es/buscar/act.php?id=BOE-A-2010-5098
- M349 current design record: https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos_20/DR_Anexo_349.pdf
