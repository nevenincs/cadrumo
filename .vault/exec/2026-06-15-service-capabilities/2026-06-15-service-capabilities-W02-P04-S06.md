---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S06'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
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
     The Add DependencyStatus + per-service probes (ollama reachability/model, playwright, google creds, provider CLIs) that never raise on absence and ## Scope

- `src/aeat/application` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add DependencyStatus + per-service probes (ollama reachability/model, playwright, google creds, provider CLIs) that never raise on absence

## Scope

- `src/aeat/application`

## Description

- Add `aeat.application.provisioning` with `DependencyStatus` + probes (ollama reachability/model via /api/tags, subprocess providers via available_llm_providers, Playwright via a fast browsers-cache filesystem scan). Probes never raise on absence.

## Outcome

Typed availability probes back the graceful-degradation paths and the doctor.

## Notes

Renamed from a diagnostics/ package that shadowed the existing diagnostics.py module (fixed in commit 16c34887b). The Playwright probe scans the cache dir rather than launching the sync driver, which hangs inside the CLI process.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
