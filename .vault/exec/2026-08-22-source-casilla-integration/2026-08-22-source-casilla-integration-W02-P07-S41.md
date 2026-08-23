---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:157ecad1df5d8218ae97a8bf6104ad7aca49a84b0cded88a38bc6e8cf7cc0e45'
step_id: 'S41'
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
     The S41 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The supply the encrypted inventory repository through calculation orchestration and ## Scope

- `src/cadrumo/application/modelo/_calculation_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# supply the encrypted inventory repository through calculation orchestration

## Scope

- `src/cadrumo/application/modelo/_calculation_actions.py`

## Description

- Compose the enrolled inventory resolver through the production bucket source mesh.
- Construct its encrypted repository only when the active revision declares an inventory binding.
- Bind secure storage explicitly to the work unit bucket and preserve canonical mesh-stage validation.
- Add real encrypted success, absence, corruption, bucket isolation, laziness, construction-count, and confidentiality proofs.

## Outcome

The production calculation action now supplies `InventorySourceResolver` with an `InventoryLedgerRepository` backed by the secure-object repository for the active work-unit bucket. Construction occurs only when the selected revision declares an inventory binding; revisions without inventory bindings allocate no inventory secure store, repository, or load.

The resolver runs once through the canonical mesh-stage guard and retains the S39 contracts for source-owned values, stable identity, sealed projection fingerprint, retained conflict diagnostics, and value-free storage degradation. No root-profile fallback, unencrypted state, alternate repository, CLI prompting, caller-override rule, registry binding, or census claim was introduced.

Independent review reported zero findings. Forty-nine broader focused tests passed, and Ruff, the focused type checker, and scoped diff hygiene were clean.

## Notes

The non-tautological orchestration tests spy on the secure factory, repository constructor and load, and route-stage guard while separately exercising real encrypted storage. Review requested a canonical `CalculationRouteStage` annotation on the route spy; the correction removed the only type-check failure before final clearance. Caller ownership remains S42 and registry bindings remain S43 and later.
