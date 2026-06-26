---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S01'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
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
     The Retire the advertised-canonical CasillaAggregation/CasillaProvenance framing from the package docstring, keeping the live ledger-aggregation classes but removing the bypassed canonical claim and ## Scope

- `src/aeat/application/aggregation/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire the advertised-canonical CasillaAggregation/CasillaProvenance framing from the package docstring, keeping the live ledger-aggregation classes but removing the bypassed canonical claim

## Scope

- `src/aeat/application/aggregation/__init__.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Commit `ae2ed0a5f`. Refined the aggregation package docstring so
`CasillaAggregation` / `CasillaProvenance` read as the per-modelo
ledger-aggregation value records produced by the `aggregate_*` family, NOT a
canonical resolved-source envelope; named `CalculationSourceResolution` as the one
canonical resolved-source envelope every mesh resolver returns.

## Outcome

P01.S01 complete. The live `CasillaAggregation` / `CasillaProvenance` classes and
re-exports are kept (coordinator adj#2); only the advertised-canonical framing is
retired. Docstring-only; no behaviour change.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Landed via explicit-pathspec commit while a peer had files staged in the shared
index, scoped to `__init__.py` only so the peer's staged work was preserved.
