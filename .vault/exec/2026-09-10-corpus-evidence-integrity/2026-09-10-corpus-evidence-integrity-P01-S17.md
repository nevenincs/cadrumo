---
tags:
  - '#exec'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c440bb9b0e6234b0a037be20b2fc30637a975590fcc17c648b5929e05244207e'
step_id: 'S17'
related:
  - "[[2026-09-10-corpus-evidence-integrity-plan]]"
---

# Re-verify every required_text phrase on the Ley 12/2002 article 29 entry against the replaced BOE text

## Scope

- `src/cadrumo/_data/registry/aeat/legal/iva.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/iva.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

The prior excerpt was not merely unattributed but substantively wrong: it gave
article 29 the invented title `Distribucion territorial de la recaudacion del
Impuesto sobre el Valor Anadido`. The real article 29 is `Gestion e inspeccion
del Impuesto`. All three former `required_text` phrases fail against the BOE text
and were replaced.
