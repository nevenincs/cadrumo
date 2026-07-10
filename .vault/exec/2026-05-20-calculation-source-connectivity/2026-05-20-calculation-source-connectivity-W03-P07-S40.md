---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S40'
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
     The S40 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Define fincas resolver adapter boundaries without enrolling calculations and ## Scope

- `src/aeat/application/aggregation/_source_fincas.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define fincas resolver adapter boundaries without enrolling calculations

## Scope

- `src/aeat/application/aggregation/_source_fincas.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Add `application/aggregation/_source_fincas.py`: `FincasSourceReadinessResolver`, which implements the source-mesh resolver shape (`resolver_id`, `owned_sources = ()`, `resolve`) but is NOT enrolled in `merge_source_resolutions`. Its `resolve` reads `fincas_source_readiness()` and returns an empty resolution carrying exactly one `source_domain_not_ready` blocked-readiness diagnostic. Add the `source_domain_not_ready` member to the `CalculationSourceDiagnosticReason` Literal.

## Outcome

The fincas source surface is provisioned as a resolver-adapter boundary that refuses visibly and enrolls nothing (owns no `BindingSourceKind`). Landed in commit `7c15ee0184`. Gates clean.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The resolver is deliberately absent from the live mesh tuple; the `fincas` diagnostic `source_kind` is a free string, not a `BindingSourceKind` member, so it cannot enter the enrolled/deferred/reserved source sets and cannot silently blank a calculation.
