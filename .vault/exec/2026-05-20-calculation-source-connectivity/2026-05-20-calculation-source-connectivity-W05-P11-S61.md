---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S61'
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
     The S61 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Run hardening pass for silent zero and missing source diagnostics and ## Scope

- `src/aeat/domain/calculations/registry` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run hardening pass for silent zero and missing source diagnostics

## Scope

- `src/aeat/domain/calculations/registry`

## Description

- Run the silent-zero / missing-source-diagnostics hardening pass and re-confirm the enrollment gate GREEN on the settled registry.

## Outcome

PASS — 9/9 green on the settled registry with NO `RegistryLoadError`. Every declared binding source is enrolled, explicitly deferred, or manual; no source-backed binding can silently calculate zero (the `no-dormant-source-resolvers` + `no-silent-under-declaration` invariants hold). This is the MANDATORY settle-window re-confirm that closes the campaign honesty-gate — a genuine green on a settled tree, not the churn-contaminated red seen during the concurrent modelo-145 export write. No hardening gap surfaced; no code fix required.

## Notes

The silent-zero hardening is structurally enforced by the enrollment + missing-source gate; this step verified it holds on the settled registry. Closes the calculation-source-connectivity campaign honesty-review.
