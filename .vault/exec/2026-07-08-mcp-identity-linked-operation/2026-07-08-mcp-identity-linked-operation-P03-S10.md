---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S10'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-identity-linked-operation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-08-mcp-identity-linked-operation-plan placeholders are machine-filled by
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
     The Add identity-gate tests: unconfirmed first mutation refuses, a prior identity read clears it, a profile switch re-arms it, and the refusals are byte-identical on both call paths and ## Scope

- `src/aeat/entrypoints/mcp/tests/test_identity_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add identity-gate tests: unconfirmed first mutation refuses, a prior identity read clears it, a profile switch re-arms it, and the refusals are byte-identical on both call paths

## Scope

- `src/aeat/entrypoints/mcp/tests/test_identity_gate.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in commit 91bcc6d34b — block-first-mutation identity gate keyed off the declared risk table, byte-identical on direct+execute paths, re-armed on profile switch; harness.load counts as an identity read; CONFIRM elicitation echoes the label (I4). D7 regression from the P01 risk table fixed in 347ee6ec0d.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
