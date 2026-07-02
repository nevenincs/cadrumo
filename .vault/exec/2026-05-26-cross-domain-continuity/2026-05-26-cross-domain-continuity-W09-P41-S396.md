---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S396'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S396 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The reconcile imputed-real-estate follow-up: current registry authors TRLIRNR Art 13.1.h, AEAT imputed-income guidance, imputation parameters, input casillas, and the `m210_resolve_base_imponible` branch for `tipo_renta=inmobiliaria` and ## Scope

- `leave unchecked until a matching exec/close record reconciles this historical step`
- `src/aeat/_data/registry/aeat/modelos/210/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# reconcile imputed-real-estate follow-up: current registry authors TRLIRNR Art 13.1.h, AEAT imputed-income guidance, imputation parameters, input casillas, and the `m210_resolve_base_imponible` branch for `tipo_renta=inmobiliaria`

## Scope

- `leave unchecked until a matching exec/close record reconciles this historical step`
- `src/aeat/_data/registry/aeat/modelos/210/`

## Description

- Ground the follow-up with `uvx vaultspec-rag search "m210_resolve_base_imponible inmobiliaria imputed real estate Art 13.1.h Modelo 210" --type code --limit 10 --port 8766 --timeout 30`.
- Inspect the plan row, M210 2025 casillas, base-imponible formula, imputed-real-estate parameters, verification predicates, TRLIRNR legal catalogue, source catalogue, runtime `m210_resolve_base_imponible` branch, and focused M210 tests.
- Confirm `trlirnr-rdleg-5-2004:art-13.1.h` is catalogued against the bundled TRLIRNR corpus and notes the live M210 imputed-real-estate branch.
- Confirm the AEAT imputed-income source `aeat-irnr-renta-imputada-inmueble-urbano` is registered and cited by the M210 inmobiliaria casillas, parameters, and base formula.
- Confirm the M210 2025 registry carries the manual inmobiliaria input casillas `valor_catastral`, `coeficiente_imputacion_inmobiliaria`, `dias_imputacion`, `valor_adquisicion`, and `valor_comprobado_administracion`.
- Confirm the M210 2025 imputation parameters carry `0.011`, `0.02`, and `0.50` for the LIRPF Art. 85 recent-revision, old/no-revision, and no-cadastral substitute-base rules.
- Confirm the `m210-base-imponible-2025` formula dispatches to `m210_resolve_base_imponible` and the runtime `tipo_renta == "inmobiliaria"` branch computes the imputed base through cadastral or substitute-value paths while rejecting invalid coefficients, missing substitute value, and disallowed expenses.
- Confirm the focused registry and application tests cover the legal/source grounding, advisory predicate, and real calculate-then-verify inmobiliaria path.

## Outcome

- No code, registry, or test edits were required. The historical imputed-real-estate follow-up is already satisfied by the current local M210 registry, legal/source catalogue, runtime, and tests.
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py -q` passed with 17 tests.
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_modelo_210_inmobiliaria_e2e.py src/aeat/domain/calculations/registry/tests/test_modelo_210_registry.py -q` passed with 18 tests.
- Closed W09.P41.S396 through the vault plan CLI after creating this matching exec record.

## Notes

- Audit note: this closure is documentation-only and reconciles a stale historical follow-up against existing implementation evidence; it does not broaden M210 Phase 2 scope.
- Shared worktree already contained extensive unrelated dirty state; this step did not revert, clean, stage, or commit unrelated files.
