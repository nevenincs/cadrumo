---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:dd1cbd90be54752d02a1034108dd4f708505dd2837edb049e1ccdfad62b64120'
step_id: 'S21'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# Author modelo 100's ten Anexo A deduction casillas that both bundled dictionaries declare and the registry omits: A/C/E vivienda habitual (LIRPF DT 18), D empresas nueva creacion and M partidos politicos and I bienes de interes cultural (art. 68), F alquiler (DT 15), G/H/J donativos which additionally need a ley-49-2002:art-19 legal entry the catalogue lacks

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas`

## Description

- Author the ten missing Anexo A deduction casillas in both current Modelo 100 revisions.
- Bind each casilla to the existing LIRPF authority and add the missing Ley 49/2002 article 19 catalogue authority for the donation rows.
- Verify both revision trees through the registry schema and legal-reference gates.

## Outcome

Commit `c7164588d7b` carries the 2024 and 2025 Anexo A registry declarations and
their legal references. Both revisions now expose the ten dictionary-declared
deduction casillas through the canonical registry authority.

## Notes

No alternative calculation or binding authority was introduced.
