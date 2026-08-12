---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:0eaa02cf80815516fefd494e82bb568fb1b9d153dcc8017ea316c470788f8ec1'
step_id: 'S31'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace casilla-schema with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S31 and 2026-08-10-casilla-schema-plan placeholders are machine-filled by
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
     The delete the strict resolve_bound_inputs_by_casilla_id and both of its facade exports and ## Scope

- `src/cadrumo/domain/calculations/registry/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# delete the strict resolve_bound_inputs_by_casilla_id and both of its facade exports

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Description

- Delete the strict registry bound-input resolver and remove its implementation-module export.
- Remove the resolver import and public-name entry from the registry package facade.
- Retarget calculation, continuity, worked-example, and scenario setup onto the living application projector.
- Remove stale strict-resolver references from application documentation and registry validation prose.
- Add a structural regression proving the application projector is the sole resolver and the retired name is absent from both registry namespaces.

## Outcome

`resolve_available_bound_inputs_by_casilla_id` remains the one public projector used by production calculate paths and test setup. The retired strict resolver has no definition, import, facade binding, `__all__` entry, alias, or compatibility shim. Unresolved-input authority remains on the existing advisory and verification paths.

Focused Ruff and BasedPyright checks passed. The structural resolver-surface regression passed serially. A serial real-registry/application selection produced nine passes and one profile-fixture failure before reaching the resolver path because `iva.m303_regime_composition` was not explicitly declared. An earlier parallel selection was invalidated by concurrent registry writes: 18 tests passed, while the remaining cases reported the registry fingerprint-churn refusal.

## Notes

No production registry data or peer-owned dirty path was edited. The registry-authority test lane was retried serially after the concurrent-write collision; the remaining failure is outside the deleted resolver surface and is recorded rather than hidden.
