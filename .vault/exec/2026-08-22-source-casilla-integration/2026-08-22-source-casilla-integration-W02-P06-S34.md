---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:77733a0bfbd6000879808bfb66a848e8a982d84fc1e4412526fb1c061fcd546a'
step_id: 'S34'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S34 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The remove or correct the stale Anexo D casilla 0155 intent after adjudication and ## Scope

- `src/cadrumo/domain/contribuyente/inventory/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# remove or correct the stale Anexo D casilla 0155 intent after adjudication

## Scope

- `src/cadrumo/domain/contribuyente/inventory/__init__.py`

## Description

- Remove the obsolete signed inventory-variation helpers and every code claim that inventory maps to casilla `0155`.
- Add a strict frozen 2025 projection that records its opening and closing basis and splits variation exclusively between `0177` and `0182`.
- Refuse unsupported years, cross-year movements, non-cent result values, and unexplained conflicts between explicit and movement-derived closing values.
- Keep acquisition cost for `0181` absent until its complete source fact is implemented, and retain the census disposition as `connect_candidate`.
- Update the reviewed capability identity and architecture wording without claiming a live inventory resolver.
- Add focused projection tests and obtain a formal code review.

## Outcome

The stale `0155` API has no compatibility alias or remaining source reference. The new projection is activity-scoped by its ledger, grounded only for 2025, auditable from its stored basis, mutually exclusive by construction, and deliberately non-authoritative for purchases. Eight projection tests plus the inventory application, encrypted persistence, and CLI payload regressions pass.

## Notes

The source-connectivity comparison and census suites could not reach this change because unrelated concurrent command-spec work is structurally unresolved in `_modelo_work_command_specs.py`. The documentation build likewise reached an unrelated missing Modelo 210 Spanish locale key; its other sixteen tests passed. The formal review reported no high or critical findings; its medium cross-period and low cent-normalisation findings were resolved before closure.
