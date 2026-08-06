---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:4824a6c35253d1a95908ef77060633c3f25daa51270662965bdf412666d5df78'
step_id: 'S81'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# author the M720 prior-year asset-baseline previous_filing binding (+20k/50k re-declaration) in the registry per A3 (RD 1065/2007 art.42-bis) (vaultspec-high-executor)

## Scope

- `src/aeat/_data/registry/aeat/modelos/720/`

## Description

- Add three strict `previous_filing` copy bindings for the closed Modelo 720 legal blocks: cuentas, valores, and inmuebles.
- Use only existing selector keys: `source_modelo`, `filing_year_delta = -1`, `period = "0A"`, and one `source_casilla_id` per binding.
- Add `inmuebles.valoracion` to the Modelo 720 revision casillas and construct membership so the third legal block has a registry source.
- Ground each binding on the matching RD 1065/2007 block article, `ley-58-2003:da-18`, and `orden-hap-72-2013:art-2`.

## Outcome

- Satisfied by `src/aeat/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/bindings/0003-prior-year-baseline-bindings.toml` and the matching construct/casilla registry edits.
- No selector schema expansion was retained; missing prior source casillas still fail strictly.

## Notes

- Explicit zero evidence is supported. A truly absent `inmuebles.valoracion` prior-year casilla is not silently invented as zero.
- Verified by the final scoped M720/M721 run, which passed 90 targeted tests after review fixes.
