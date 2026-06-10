---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
step_id: 'S11'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-operator-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# run a feasibility spike on deferring help-text rendering until after eager-option resolution to determine whether --language can be made to actually localize help text without destabilising the import-time i18n model

## Scope

- `src/aeat/entrypoints/cli/__init__.py`

## Description

- Reproduce the silent failure: `aeat --language en config profile create --help` renders Spanish, while `AEAT_OUTPUT_LANGUAGE=en` set before the process renders English.
- Instrument `override_settings` and trace the root callback against a leaf `SUB --help` invocation.
- Prototype a pre-parse that reads `--language` from argv and sets `AEAT_OUTPUT_LANGUAGE` before the lazy command tree imports.

## Outcome

Spike verdict: **make-it-work is feasible-and-cheap** via an argv pre-parse in the console entry point.

Two structural blockers explain the current silent failure. First, the root group callback's `override_settings(aeat_output_language=...)` is **never reached** for a leaf `SUB --help`: click short-circuits the leaf `--help` before the root group callback body runs (traced empirically — the override trace never fired). Second, every help string is rendered by `tr(...)` at module-import time when the Typer options/groups are constructed, so the language for a help string is frozen at import. Deferring help rendering across the whole surface would destabilise the import-time i18n model and is the invasive path the operator caveat forbids.

The cheap make-it-work path works *with* the import-time model rather than against it: the profile-owned output-language resolver reads `AEAT_OUTPUT_LANGUAGE` before import, and the leaf subcommand modules import lazily *after* the console `main()` runs. A pure argv scan in `main()` that promotes `--language` to the env var before dispatch makes the lazily-imported leaf help render in the chosen language. Root-level `--help` already honours `--language` (it builds an invocation-time operator-surface document), so only leaf/group click help was dishonest, and the pre-parse closes exactly that gap.

## Notes

The prototype was validated against the real installed console before implementation: `--language en` → English leaf help, `--language es` → Spanish, no flag → default. No rendering interception or deferred-render refactor was needed.
