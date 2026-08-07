---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f8690b98e2552e4c829c9ce06594755b9f42b00991d83594ac24cb23e60d037e'
step_id: 'S37'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S37

## Outcome

**FETCH-GATED**, using the project's established disposition for a step that needs an official artefact the tree does not carry. The gate is not a deferral: the Modelo 210 precedent shows the same marker resolved by fetching, bundling and sha256-pinning the named document.

## What is missing, verified from the source workbook

`W03.P04` reported the code table absent, reading the extracted markdown. That reading was re-taken here against the **workbooks themselves**, because a file-shape assumption is exactly what undercounts a bundled corpus:

- All five bundled M036 workbooks carry only page sheets (`Pag. 0` through `Pag. 10`). There is no `Tabla` sheet in any of them.
- Searching every cell of every sheet for the activity vocabulary returns the field declaration and nothing else:

      [Pag. 4]  6 | 76 | 3 | An | Actividad. Tipo de actividad.  [403]  |  Tabla

- The omission is legible rather than accidental. Neighbouring fields enumerate their code sets inline in that same column — the IVA régimen especial agricultura field beside it spells out `1 - incluido/2- excluido/3- renuncia/4-revocacion/5-baja`. This one says only `Tabla`.
- The IRPF section repeats the field per activity slot at `[613]` and `[614]`, also three alphanumeric characters, also table-sourced.

So the value set genuinely lives in a document AEAT publishes alongside the diseño, not inside it.

## Why the existing sync tool does not close this

`dev/corpus/sync_aeat_record_design_corpus.py` synchronises the **diseño de registro** indexes from the Sede static-files endpoint. The M036 diseño is already bundled and is the very artefact that declines to enumerate the table. The tool would re-fetch what is already here.

## Why it was not fetched ad hoc

Bundling a corpus artefact carries provenance discipline the precedent makes explicit: a per-modelo `manifest.json` entry with stored path, sha256, byte count and source URL, so the record-design catalogue gate can resolve it. Pulling a page with an arbitrary fetch and dropping the bytes in would create exactly the artefact-outside-the-declared-manifest condition that `W05.P07.S32` was written about.

## What unblocks, once it lands

`S38` grounds the code-to-partition mapping against it, `S11` places the activity-type axis that mapping populates, and `S13` aggregates M130 casilla 08 using that axis. All three are marked with their blocker so none is attempted first.

The alternative — inferring the partition from the codes without the table — is the fabricated-grounding failure `legal-grounding-verifies-bundled-authoritative-corpus` names, and it would sit underneath a rate screen where nothing downstream could detect it.
