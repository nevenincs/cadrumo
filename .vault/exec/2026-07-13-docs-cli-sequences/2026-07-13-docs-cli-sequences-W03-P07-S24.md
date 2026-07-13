---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S24'
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
     The S24 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Teach the conformance gate the sequence grammar (strip @setup and @result sigils, treat {name} as a positional placeholder) and add the enrolled-page no-plain-executable-fence tier and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Teach the conformance gate the sequence grammar (strip @setup and @result sigils, treat {name} as a positional placeholder) and add the enrolled-page no-plain-executable-fence tier

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

- Teach the documented-command conformance gate the cli-sequence grammar: make `{name}` interpolation tokens an explicit positional-placeholder class in the line parser, and document that a `@setup` / `@result` frame sigil precedes the `aeat` token and is dropped by the existing executable anchor while `@capture` / `@expect` lines carry no `aeat` token and are skipped upstream.
- Add the enrolled-page tier: detect a page carrying at least one `{cli-sequence}` directive, and on such a page refuse a plain fenced block that carries a concrete executable `aeat` invocation while exempting the directive's own fences and permitting narrative inline references.
- Add fixture-based tests proving a directive body's frame lines are extracted and conform to the live CLI, and that an enrolled page with a plain executable fence is refused while an all-executed enrolled page and a non-enrolled page are clean.
- Add a live-scan gate over the shipped doc surface that applies the enrolled refusal to every enrolled page, so real enrolled pages are gated the moment they land without an implicit skip today.

## Outcome

- The full conformance module is green (56 tests), including the anti-vacuity floor and value-consuming-option resolution the W01 repair introduced, which were extended without weakening.
- Non-enrolled pages keep exactly today's verb-path and option-name checks; the enrolled tier is additive.
- Ruff and ty are clean.

## Notes

- The `@setup` / `@result` sigil stripping was already incidental via the `aeat` anchor and `{name}` already fell through to positional; the change makes both intentional and test-locked rather than relying on incidental behaviour.
- The enrolled live-scan is currently vacuous-but-not-skipped (no enrolled pages ship yet); it becomes load-bearing with the first tutorial wave.
