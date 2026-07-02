---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S395'
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
     The S395 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The reconcile Art 25.1.b pension follow-up: current registry implements `m210-pension-tarifa-2025` as a three-tranche bracket table (8%, 30%, 40%) and AR/pension delegates through `DOMESTIC_TARIFF` and ## Scope

- `leave unchecked until a matching exec/close record reconciles this historical step`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0004-m210-pension-tarifa-2025.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# reconcile Art 25.1.b pension follow-up: current registry implements `m210-pension-tarifa-2025` as a three-tranche bracket table (8%, 30%, 40%) and AR/pension delegates through `DOMESTIC_TARIFF`

## Scope

- `leave unchecked until a matching exec/close record reconciles this historical step`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0004-m210-pension-tarifa-2025.toml`

## Description

- Ground the follow-up with `uvx vaultspec-rag search "m210-pension-tarifa-2025 Art 25.1.b AR pension DOMESTIC_TARIFF" --type code --limit 10 --port 8766 --timeout 30`.
- Inspect the plan row, `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0004-m210-pension-tarifa-2025.toml`, `src/aeat/_data/registry/aeat/treaties/es-ar.toml`, and `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`.
- Confirm `m210-pension-tarifa-2025` is a `bracket_table` grounded in `trlirnr-rdleg-5-2004:art-25.1.b` with brackets `0` to `12000` at `0.08`, `12000` to `18700` at `0.30` with `960` fixed addition, and excess over `18700` at `0.40` with `2970` fixed addition.
- Confirm the Spain-Argentina pension override uses `allocation_domestic_tariff`, has no fixed scalar rate, and carries both `convenio-es-ar-1992:art-19` and `trlirnr-rdleg-5-2004:art-25.1.b`.
- Confirm the focused M210 convenio-rate regression pins the AR/pension `ALLOCATION_DOMESTIC_TARIFF` row and the Felipe AR/pension no-blocking scalar-helper behavior.

## Outcome

- No code, registry, or test edits were required. The historical Art 25.1.b pension follow-up is already satisfied by the current local registry and treaty authority.
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py -q` passed with 17 tests.
- Closed W09.P41.S395 through the vault plan CLI after creating this matching exec record.

## Notes

- Audit note: local registry/source refs are the authority for this closure; the orchestrator-supplied consolidated TRLIRNR Art. 25.1.b context agrees with the same three-tranche pension scale.
- Shared worktree already contained extensive unrelated dirty state; this step did not revert, clean, stage, or commit unrelated files.
