---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:4531e58c3a042d795dffe8c7ad4b03fe82465b2a46e1869885271def9f860eb6'
step_id: 'S45'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S45 and 2026-08-24-registry-completeness-closure-plan placeholders are machine-filled by
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
     The Revalidate connected census claims through live source proof authority at composition time and refuse proof loss or digest mismatch. and ## Scope

- `src/cadrumo/application/registry/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Revalidate connected census claims through live source proof authority at composition time and refuse proof loss or digest mismatch.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Revalidate every connected census row through the live source-connectivity proof authority when composing a closure report.
- Convert a missing, lost, or digest-divergent live proof into an evidence-bearing refused source-connectivity limb.
- Exercise the report boundary against a real encrypted calculation-revision repository, then mutate executable evidence after the initial report.

## Outcome

- Connected claims no longer remain terminal merely because an earlier census load passed live proof validation.
- A changed executable-evidence digest changes the affected source limb from satisfied to refused with an actionable owner disposition.
- Passed focused Ruff, five unit coverage tests, and the real integration digest-drift regression.

## Notes

- The default focused test command selects unit tests and intentionally deselects the real integration proof; the integration test was run explicitly with the integration marker.
