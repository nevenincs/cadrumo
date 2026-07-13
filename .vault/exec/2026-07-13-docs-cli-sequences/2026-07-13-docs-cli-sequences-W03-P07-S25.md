---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S25'
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
     The S25 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Write directive and tokeniser tests asserting the payload shape, token classification, and no-JS static frame HTML and ## Scope

- `dev/docs/tests/test_sequence_directive.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Write directive and tokeniser tests asserting the payload shape, token classification, and no-JS static frame HTML

## Scope

- `dev/docs/tests/test_sequence_directive.py`

## Description

- Add a two-tier gate for the directive and tokeniser with no mocks or skips.
- Pure-function tier: assert the tokeniser classifies verbs, options, option values, and `{name}` placeholders against the live tree and carries the space-joined command-path key; assert the payload shape and that the static HTML renders from the one payload with the inline JSON parsing equal to the computed payload; assert a stale golden (frame-count mismatch) is refused.
- Real-build tier: build a minimal in-process MyST Sphinx site with the directive registered and a committed golden fixture, and assert the rendered `index.html` carries the server-side static frames (the no-JS transcript), the tokenised spans, and one well-formed inline payload matching the four frames.
- Assert a directive whose golden is absent fails the build with an instructive message naming the exact refresh invocation and renders no sequence container.
- Pin an isolated Cadrumo storage root and English output for the CLI-tree walk via a fixture, and redirect the directive at the fixture golden tree through the Sphinx config value.

## Outcome

- Six tests pass, including the two real Sphinx builds; the directive and tokeniser are proven end to end through a genuine build, not a stubbed render.
- Ruff and ty are clean.

## Notes

- The golden fixtures are constructed through the strict `SequenceGolden` model (schema-valid by construction) in a temp tree, not hand-edited committed goldens, so the CLI-owned golden discipline is preserved.
