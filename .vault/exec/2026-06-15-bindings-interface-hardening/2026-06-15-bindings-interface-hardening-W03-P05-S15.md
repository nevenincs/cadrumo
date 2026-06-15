---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S15'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The wire the per-family unrouted-observation advisory diagnostics on the live calculate path so a resolver surfaces an advisory instead of a silent Decimal(0) and ## Scope

- `src/aeat/application/modelo/_calculation_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# wire the per-family unrouted-observation advisory diagnostics on the live calculate path so a resolver surfaces an advisory instead of a silent Decimal(0)

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Locate the IVA screen's live caller: the IVA mesh resolver already projects unrouted IVA observations into `CalculationSourceDiagnostic` advisories on each resolve.
- Wire the renta-expense and renta-income screens onto their resolvers in `_modelo_bindings.py`, emitting one `unrouted_observation` advisory per unrouted observation through the same diagnostics channel.
- Wire the OSS screen onto its resolver in `_oss_ioss.py`, emitting the advisory for the candidate-present case (the no-live-source case keeps its existing `oss_no_live_source` advisory).
- Align the existing IVA unconsumed-observation diagnostic from `source_issue` to the new `unrouted_observation` reason for uniformity across families.

## Outcome

Every live aggregation family now surfaces an advisory (non-blocking) `CalculationSourceDiagnostic` on the calculate path when a non-zero declarable observation routes to no binding, instead of silently resolving the casilla to zero. Calculate still succeeds; the diagnostic rides the shared mesh diagnostics channel.

## Notes

The advisory is emitted, never swallowed. The reason rename on the IVA diagnostic is safe: the existing IVA test filters on `source_kind` plus message substring, not the reason string.
