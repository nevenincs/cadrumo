---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:a9b41ef3da0e85868d197a33ec94d33628feb767c54ce73a577ec646bae7a2a9'
step_id: 'S24'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

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
