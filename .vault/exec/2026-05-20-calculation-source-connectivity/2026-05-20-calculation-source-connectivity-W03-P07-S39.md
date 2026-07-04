---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S39'
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
     The S39 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Define fincas calculation source readiness diagnostics and ## Scope

- `src/aeat/domain/fincas/_source_readiness.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define fincas calculation source readiness diagnostics

## Scope

- `src/aeat/domain/fincas/_source_readiness.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Add `domain/fincas/_source_readiness.py`: a pure-domain `FincasSourceReadiness` (strict-frozen `ready` / `source_kind` / `reason`) and a `fincas_source_readiness()` returning `ready = False`, because the fincas rendimiento and amortization aggregates are not persisted through the canonical secure-storage revision boundary. Export the surface from the fincas package facade.

## Outcome

The fincas calculation-source readiness is a context-independent domain fact the aggregation resolver reads. Landed in commit `7c15ee0184`. Gates clean.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Implements the fincas half of the calculation-source-connectivity ADR Phase 8 ("enroll fincas and inventory only after persistence hardening"): the readiness declares fincas NOT ready so the surface refuses visibly rather than resolving a silent blank (`no-dormant-source-resolvers`).
