---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S41'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S41 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Define inventory calculation source readiness diagnostics and ## Scope

- `src/aeat/application/inventory/_source_readiness.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define inventory calculation source readiness diagnostics

## Scope

- `src/aeat/application/inventory/_source_readiness.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Add `application/inventory/_source_readiness.py`: an `InventorySourceReadiness` (strict-frozen `ready` / `source_kind` / `reason`) and an `inventory_source_readiness()` returning `ready = False`, because inventory is an application service over profile inventory whose movements and valuations are not persisted through the canonical secure-storage revision boundary. Export the surface from the inventory package facade.

## Outcome

The inventory calculation-source readiness is a context-independent fact the aggregation resolver reads. Landed in commit `7c15ee0184`. Gates clean.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Inventory readiness lives at the application layer (not domain) because inventory is an application service, unlike the fincas domain in S39. Implements the inventory half of the ADR Phase 8 deferral: NOT ready, so the surface refuses visibly.
