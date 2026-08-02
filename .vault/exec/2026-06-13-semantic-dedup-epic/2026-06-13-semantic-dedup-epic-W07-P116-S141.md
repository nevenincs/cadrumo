---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:12a522631b41a269f5bc9002d35feefed485e5889acb81994958bd9850b7b4c3'
step_id: 'S141'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S141 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The Centralize anchored extracted-corpus resolution, refuse missing or duplicate anchors, and prove registry verification and citation lookup cannot fall back to unrelated units. and ## Scope

- `src/cadrumo/domain/calculations/registry/_legal.py`
- `src/cadrumo/application/corpus_search/_citation_lookup.py`
- `legal grounding and citation lookup tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Centralize anchored extracted-corpus resolution, refuse missing or duplicate anchors, and prove registry verification and citation lookup cannot fall back to unrelated units.

## Scope

- `src/cadrumo/domain/calculations/registry/_legal.py`
- `src/cadrumo/application/corpus_search/_citation_lookup.py`
- `legal grounding and citation lookup tests`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
