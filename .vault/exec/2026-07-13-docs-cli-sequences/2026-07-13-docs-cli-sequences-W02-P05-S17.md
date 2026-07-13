---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S17'
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
     The S17 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Implement the check CLI mode that fails with the page, sequence id, frame index, argv, differing_paths or unified diff, and the exact refresh invocation and ## Scope

- `dev/docs/sequences/__main__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the check CLI mode that fails with the page, sequence id, frame index, argv, differing_paths or unified diff, and the exact refresh invocation

## Scope

- `dev/docs/sequences/__main__.py`

## Description

- Implement `check_sequences` — THE engine check function both future gate surfaces (the Sphinx builder-inited hook and the dev-docs pytest gate, plan W03.P08) call, so a divergence reds every surface through one execution-and-comparison path.
- For each discovered sequence: read the committed golden (a missing or hand-corrupted golden is a named problem carrying the exact refresh invocation), re-execute in a fresh hermetic sandbox, and run the shared `check_transcript` tier (golden comparison plus live `@expect` evaluation).
- Implement the `check` CLI mode: exit 0 with a clean summary, exit 1 printing every FAIL line — page, sequence id, frame index, argv, post-mask differing paths or unified text diff — and a closing remedy line with the exact scoped refresh invocation.
- Cover the mode with real tests: clean pass after a real refresh, golden-mutation drift naming the frame and path and remedy, missing-golden refusal, and a direct `check_sequences` call proving the CLI wraps the same function the gates will.

## Outcome

A wrong writeup, a renamed verb, a changed output shape, or a CLI regression fails the check with a named sequence, frame, and diff, plus the one command that updates the golden — the ADR's operator-facing failure contract, end to end.

## Notes

No incidents.
