---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e127491eff182f3e3b4fb4fcef6d0f170da3adfe628cca4efa328ee3ac298761'
step_id: 'S21'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-suite-red-at-head with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-08-13-registry-suite-red-at-head-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Author modelo 100's ten Anexo A deduction casillas that both bundled dictionaries declare and the registry omits: A/C/E vivienda habitual (LIRPF DT 18), D empresas nueva creacion and M partidos politicos and I bienes de interes cultural (art. 68), F alquiler (DT 15), G/H/J donativos which additionally need a ley-49-2002:art-19 legal entry the catalogue lacks and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
