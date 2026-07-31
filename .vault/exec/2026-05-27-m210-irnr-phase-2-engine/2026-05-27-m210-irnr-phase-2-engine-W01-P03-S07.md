---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:64febe04622ff0bc6bf80b95b2276064779806d92a4eac86398379ce5080f09d'
step_id: 'S07'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# FETCH-GATED (fetch: AEAT Sede "Disenos de registro - modelo 210" or the official M210 Sede form specimen) - fetch and bundle the official complete M210 field enumeration as a `layout_authority` corpus source

## Scope

- `src/aeat/_data/corpus/normatives/html`

## Description

- Fetch the official AEAT diseño-de-registro specimen for Modelo 210 (record identifier `T21001`, version 1.1, dated 15/02/2012) from the Sede static-files endpoint and bundle it under `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_210/dr210_2011.pdf` (48190 bytes, sha256 `41875d015c809fc303a399581d6a437255f3235f8727515fe7e47606772a45e3`).
- Read the PDF and confirm the numbered liquidación field enumeration `[4]`-`[31]` directly from page 2 rather than assuming the spec figure; verify the declared inter-casilla formulas including `[8]=[5]-[6]-[7]`, `[17]=[12]+[16]`, `[24]=[22]-[23]`, `[27]=[24]-[26]`, `[28]=[24]-[27]`, and `[31]=[28]-[29] ± [30]`.
- Register the artefact as a `layout_authority` source `boe-modelo-210-diseno-registro-2011` in the IRNR legal catalogue.
- Add the per-modelo corpus `manifest.json` (following the Modelo 036 diseño-de-registro bundling precedent) so the record-design catalogue gate resolves the artefact by stored path, sha256, bytes, and source URL.

## Outcome

The official record layout is bundled and sha256-pinned, and the record-design source-catalogue gate passes. The enumeration used by S08 is grounded against the bundled authority, not against an unverified figure.

## Notes

The plan Step row anticipated the corpus path `src/aeat/_data/corpus/normatives/html`; the layout specimen is a PDF, so it was bundled under `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_210/` alongside the per-modelo `manifest.json`, matching the Modelo 036 diseño-de-registro precedent. `pdftoppm` is absent in this environment; the enumeration was extracted with `pypdf` text extraction. Committed in the same explicit-pathspec commit as S08.
