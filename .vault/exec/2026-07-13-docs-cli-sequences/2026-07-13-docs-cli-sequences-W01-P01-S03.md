---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S03'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Triage and fix every documented-command defect the repaired gate surfaces across the how-to, tutorial, explanation, and runbook doc pages and ## Scope

- `docs/how-to` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Triage and fix every documented-command defect the repaired gate surfaces across the how-to, tutorial, explanation, and runbook doc pages

## Scope

- `docs/how-to`

## Description

- Triage the repaired gate's surfaced inventory across the how-to, tutorial, explanation, and runbook doc pages.
- Reconcile the sibling self-referential-string gate that imports the renamed token symbol, whose activation surfaced one latent scanning defect.

## Outcome

No documented-command doc defects to fix: the repaired documented-command gate is green across all 58 scanned pages with zero violations (591 invocations, 1096 option tokens). The mandated burndown surface is empty — the docs already conform to the live CLI on verb path, option name, and subcommand shape.

Reconciling the renamed symbol re-activated the sibling `test_self_referential_string_conformance.py` gate, which was equally vacuous (it scanned runtime `default_suggestion` / `cli.*` locale / Python-literal next-action strings for the old `cadrumo` token while those strings cite `aeat`). Its `_cited_from_text` helper prepended the literal `"cadrumo "` and relied on `_parse_command_line` matching that token; after the anchor move it must prepend `"aeat "`. Fixed the prepend token and aligned the `after_cadrumo` parameter name to `after_aeat`. With the anchor corrected, the sibling gate's registry-suggestion, locale-string, and literal-hint scanning are all active again and resolve clean.

## Notes

The `'aeat app modelo work calculate'` literal-hint failure was a mechanical consequence of the token rename inside the sibling gate's own helper, not a production next-action string bug — the string resolves against the live CLI once the helper prepends the correct executable token. No production CLI code was changed; nothing was triaged as a CLI bug.
